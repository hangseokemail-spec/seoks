#!/usr/bin/env python3
"""Seoks 데이터 수집·계산.

필요한 환경변수: FINVIZ_AUTH (finviz Elite export 토큰), FRED_KEY (FRED API 키)
키는 절대 저장소에 쓰지 않는다.

출력
  data/series.json        날짜별 지수·지표 원값·점수·종합점수 (2023-01~)
  data/board/<날짜>.json   증시현황판 (finviz 스냅샷이 있는 날만)
  data/corr.json          점수 구간별 이후 수익률, 26주 이동 상관
  data/latest.json        최신 날짜, 현황판 날짜 목록, 지표별 관측일
  data/hist/*.json        누적 기록 (Breadth, S&P500 200일선 상회 비율)
입력
  data/manual.json        웹에서 확인하는 지표 (CNN F&G, AAII, Put/Call, Margin debt)
  data/comments/<날짜>.json  Claude 코멘트 (이 스크립트는 건드리지 않음)
"""
import argparse, csv, io, json, math, os, re, sys, time, urllib.request, datetime as dt
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
FINVIZ = os.environ.get("FINVIZ_AUTH", "")
FRED_KEY = os.environ.get("FRED_KEY", "")
START = "2023-01-03"          # 화면·상관용 시작일
FETCH_START = "2021-06-01"     # 3개월·1년 변화율 계산용 여유

# ---------------------------------------------------------------- 공통

_CACHE = {}


def http(url, timeout=60, tries=3):
    if url in _CACHE and "export/screener" not in url:
        return _CACHE[url]
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "seoks-dashboard/1.0"})
            b = urllib.request.urlopen(req, timeout=timeout).read()
            _CACHE[url] = b
            return b
        except Exception as e:  # noqa
            last = e
            time.sleep(2 + 2 * i)
    raise RuntimeError(f"fetch failed: {url.split('?')[0]} ({last})")


def jload(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default


def jsave(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))


def rnd(v, n=2):
    if v is None or (isinstance(v, float) and (math.isnan(v) or math.isinf(v))):
        return None
    return round(float(v), n)

# ---------------------------------------------------------------- 수집


def fred(sid):
    u = (f"https://api.stlouisfed.org/fred/series/observations?series_id={sid}"
         f"&api_key={FRED_KEY}&file_type=json&observation_start={FETCH_START}")
    d = json.loads(http(u))
    s = pd.Series({pd.Timestamp(o["date"]): float(o["value"]) for o in d["observations"] if o["value"] != "."})
    return s.sort_index()


def naver_foreign(code):
    end = (dt.date.today() + dt.timedelta(days=1)).strftime("%Y%m%d")
    u = (f"https://api.stock.naver.com/chart/foreign/index/{code}/day?"
         f"startDateTime={FETCH_START.replace('-', '')}0000&endDateTime={end}0000")
    d = json.loads(http(u))
    s = pd.Series({pd.Timestamp(x["localDate"]): float(x["closePrice"]) for x in d})
    return s.sort_index()


def naver_kospi():
    x = http("https://fchart.stock.naver.com/sise.nhn?symbol=KOSPI&timeframe=day&count=1500&requestType=0").decode("euc-kr")
    rows = re.findall(r'data="(\d{8})\|[^|]*\|[^|]*\|[^|]*\|([^|]*)\|', x)
    return pd.Series({pd.Timestamp(a): float(b) for a, b in rows}).sort_index()


def finviz_quote(t):
    b = http(f"https://elite.finviz.com/quote_export.ashx?t={t}&p=d&auth={FINVIZ}")
    df = pd.read_csv(io.BytesIO(b))
    df["Date"] = pd.to_datetime(df["Date"], format="%m/%d/%Y")
    return df.set_index("Date").sort_index()


def finviz_screen(filters, order=None):
    u = f"https://elite.finviz.com/export/screener?type=stocks&v=111&f={filters}&auth={FINVIZ}"
    if order:
        u += f"&o={order}"
    txt = http(u, timeout=120).decode("utf-8", "replace")
    time.sleep(0.8)
    return list(csv.DictReader(io.StringIO(txt)))

def finviz_intraday(t, date):
    """finviz 5분봉(봉 시작 시각)에서 정규장 09:30~15:55 봉 → 마지막 봉 종가 = 16:00 종가."""
    try:
        b = http(f"https://elite.finviz.com/quote_export.ashx?t={t}&p=i5&auth={FINVIZ}")
        df = pd.read_csv(io.BytesIO(b))
        # finviz는 24시간 표기에 AM/PM이 붙어 나옴 ("19:55 PM") → 접미사 제거
        df["ts"] = pd.to_datetime(df["Date"].str.replace(r"\s*[AP]M$", "", regex=True), format="%m/%d/%Y %H:%M")
        reg = df[(df.ts.dt.time >= dt.time(9, 30)) & (df.ts.dt.time < dt.time(16, 0))]
        day = reg[reg.ts.dt.date == date.date()]
        prev = reg[reg.ts.dt.date < date.date()]
        if len(day) < 10:
            return None
        return {"src": t, "pts": [rnd(x, 3) for x in day.Close.values], "prev": rnd(prev.Close.iloc[-1], 3) if len(prev) else None,
                "t0": day.ts.iloc[0].strftime("%H:%M"), "t1": day.ts.iloc[-1].strftime("%H:%M")}
    except Exception as e:  # noqa
        print("  장중 데이터 실패", t, e)
        return None


def naver_kospi_intraday(date):
    try:
        d = date.strftime("%Y%m%d")
        x = json.loads(http(f"https://api.stock.naver.com/chart/domestic/index/KOSPI/minute?startDateTime={d}0000&endDateTime={d}2359"))
        pts = [float(v["currentPrice"]) for v in x]
        if len(pts) < 10:
            return None
        return {"src": "KOSPI", "pts": [rnd(v, 2) for v in pts[::5]] + ([rnd(pts[-1], 2)] if (len(pts) - 1) % 5 else []), "prev": None,
                "t0": x[0]["localDateTime"][8:12], "t1": x[-1]["localDateTime"][8:12]}
    except Exception as e:  # noqa
        print("  코스피 장중 실패", e)
        return None

# ---------------------------------------------------------------- 점수표
# hi: 값이 클수록 점수가 높음 (cuts = 5점/4점/3점/2점 경계, 초과 기준)
# lo: 값이 작을수록 점수가 높음 (cuts = 5점/4점/3점/2점 경계, 미만 기준)


def s_hi(v, cuts):
    if v is None or pd.isna(v):
        return None
    for sc, c in zip((5, 4, 3, 2), cuts):
        if v > c:
            return sc
    return 1


def s_lo(v, cuts):
    if v is None or pd.isna(v):
        return None
    for sc, c in zip((5, 4, 3, 2), cuts):
        if v < c:
            return sc
    return 1


def s_fg(v):
    return s_hi(v, (75, 55, 44, 24))          # CNN: 76+ 극단적 탐욕, 56-75 탐욕, 45-55 중립, 25-44 공포


def s_y10(level, chg_bp):
    if level is None or chg_bp is None or pd.isna(level) or pd.isna(chg_bp):
        return None
    base = 5 if chg_bp <= -40 else 4 if chg_bp <= -10 else 3 if chg_bp < 10 else 2 if chg_bp < 40 else 1
    if level >= 4.5:
        base -= 1
    return max(1, base)


TC = {  # 트렌드캐치 9개 (단순평균)
    "fg":     lambda v: s_fg(v),
    "aaii":   lambda v: s_hi(v, (30, 20, -20, -30)),
    "vix":    lambda v: s_lo(v, (15, 20, 30, 40)),
    "hy":     lambda v: s_lo(v, (3.0001, 4.0001, 5.0001, 7.0001)),
    "pc":     lambda v: s_lo(v, (0.4, 0.5, 1.0, 1.2001)),
    "margin": lambda v: s_hi(v, (40, 20, -20, -30)),
    "a200":   lambda v: s_hi(v, (70, 60, 30, 20)),
    "rsi":    lambda v: s_hi(v, (70, 60, 30, 20)),
    "dev":    lambda v: s_hi(v, (15, 10, -10, -15)),
}
LQ = {  # 유동성 11개 (가중평균)
    "fed":    lambda v: s_hi(v, (5, 2, -2, -5)),
    "nl":     lambda v: s_hi(v, (8, 3, -3, -8)),
    "m2":     lambda v: s_hi(v, (8, 4, 0, -2)),
    "effr":   lambda v: s_lo(v, (-0.4999, -0.0999, 0.1, 0.5)),
    "hy":     lambda v: s_lo(v, (3.0001, 4.0001, 5.0001, 7.0001)),
    "dxy":    lambda v: s_lo(v, (-4.9999, -1.9999, 2, 5)),
    "margin": lambda v: s_hi(v, (40, 20, -20, -30)),
    "bank":   lambda v: s_hi(v, (10, 5, 0, -3)),
    "vol":    lambda v: s_hi(v, (150, 120, 80, 60)),
    "nfci":   lambda v: s_lo(v, (-0.5, -0.2, 0.2001, 0.5001)),
    "y10":    None,  # s_y10 (수준+13주 변화)
}
# 가중치는 data/weights.json (scripts/weights.py) — 2주마다 Claude Fable이 점검


def label_tc(x):
    if x is None:
        return None
    return "광기" if x >= 4.5 else "과열" if x >= 3.5 else "중립" if x >= 2.5 else "불안" if x >= 1.5 else "공포"


def label_lq(x):
    if x is None:
        return None
    return "풍부" if x >= 4.5 else "우호" if x >= 3.5 else "중립" if x >= 2.5 else "긴축" if x >= 1.5 else "경색"

# ---------------------------------------------------------------- 시계열 유틸
# FRED 관측일 → 실제 공개일 (미리보기 편향 방지)
LAG = {"WALCL": 1, "WTREGEN": 1, "RRPONTSYD": 0, "M2SL": 55, "EFFR": 1, "BAMLH0A0HYM2": 1,
       "TOTBKCR": 9, "NFCI": 5, "DGS10": 1, "VIXCLS": 0}
# 다음 발표 전까지 가장 최근 값을 쓰되, 수집이 끊긴 경우를 막기 위한 상한(일)
STALE = {"WALCL": 30, "WTREGEN": 30, "RRPONTSYD": 10, "M2SL": 130, "EFFR": 10, "BAMLH0A0HYM2": 10,
         "TOTBKCR": 35, "NFCI": 30, "DGS10": 10, "VIXCLS": 10}


def asof(series, dates, lag=0, stale=9999):
    """dates 각 날짜에 공개되어 있던 최신 값과 그 관측일."""
    s = series.dropna()
    avail = pd.DataFrame({"avail": s.index + pd.Timedelta(days=lag), "obs": s.index, "v": s.values}).sort_values("avail")
    left = pd.DataFrame({"d": dates}).sort_values("d")
    m = pd.merge_asof(left, avail, left_on="d", right_on="avail", direction="backward")
    m.loc[(m["d"] - m["obs"]).dt.days > stale, "v"] = np.nan
    m = m.set_index("d")
    return m["v"].reindex(dates), m["obs"].reindex(dates)


def pct_change_days(series, dates, days, lag=0, stale=9999):
    now, obs = asof(series, dates, lag, stale)
    past, _ = asof(series, dates - pd.Timedelta(days=days), lag, 9999)
    past.index = dates
    return (now / past - 1) * 100, obs


def rsi14(close):
    d = close.diff()
    up = d.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / 14, adjust=False).mean()
    return 100 - 100 / (1 + up / dn)

# ---------------------------------------------------------------- 수동(웹) 지표


def manual_series(manual, dates):
    out, obs = {}, {}
    def mk(items, key, stale, lag=0, datekey="date"):
        if not items:
            return pd.Series(np.nan, index=dates), pd.Series(pd.NaT, index=dates)
        s = pd.Series({pd.Timestamp(i[datekey]): i[key] for i in items if i.get(key) is not None}).sort_index()
        return asof(s, dates, lag, stale)
    # 가장 최근 발표값 사용 (일간 10일, 주간 30일 상한), 관측일은 화면에 표시
    out["fg"], obs["fg"] = mk(manual.get("fg"), "value", 10)
    out["pc"], obs["pc"] = mk(manual.get("pc"), "value", 10)
    out["aaii"], obs["aaii"] = mk(manual.get("aaii"), "spread", 30)
    # Margin debt: 월말 기준, 다음 달 3주차 공개 → 관측일=월말, 공개 지연 21일
    mm = manual.get("margin") or []
    if mm:
        me = lambda m: pd.Timestamp(m + "-01") + pd.offsets.MonthEnd(0)
        ms = {me(i["month"]): float(i["value"]) for i in mm if i.get("value") is not None}
        yoy = {}
        for k, v in ms.items():  # 날짜로 12개월 전 값을 찾음 (빠진 달이 있어도 안전)
            prev = (k - pd.DateOffset(years=1)) + pd.offsets.MonthEnd(0)
            if prev in ms:
                yoy[k] = (v / ms[prev] - 1) * 100
        for i in mm:  # 발표된 YoY가 있으면 그 값을 우선
            if i.get("yoy") is not None:
                yoy[me(i["month"])] = float(i["yoy"])
        out["margin"], obs["margin"] = asof(pd.Series(yoy).sort_index(), dates, 21, 120)
    else:
        out["margin"], obs["margin"] = pd.Series(np.nan, index=dates), pd.Series(pd.NaT, index=dates)
    return out, obs

# ---------------------------------------------------------------- 메인 계산


def build_series():
    print("[1/4] 시세·거시 데이터 수집", flush=True)
    F = {s: fred(s) for s in LAG}
    idx = {k: naver_foreign(c) for k, c in
           [("spx", ".INX"), ("ixic", ".IXIC"), ("dji", ".DJI"), ("ndx", ".NDX"), ("vix", ".VIX"), ("dxy", ".DXY")]}
    kospi = naver_kospi()
    spy = finviz_quote("SPY")
    vti = finviz_quote("VTI")

    dates = idx["spx"].loc[START:].index
    dates = pd.DatetimeIndex(dates)
    col, obs = {}, {}

    for k in ["spx", "ixic", "dji", "ndx", "vix", "dxy"]:
        col[k] = idx[k].reindex(dates).ffill(limit=2)
    # 코스피: 같은 날짜 종가 + 미국 t일 다음 한국 거래일 종가(상관용)
    col["kospi"] = kospi.reindex(dates, method="ffill")
    nxt = kospi.index.searchsorted(dates, side="right")
    col["kospi_next"] = pd.Series([kospi.iloc[i] if i < len(kospi) else np.nan for i in nxt], index=dates)
    col["us10y"], obs["us10y"] = asof(F["DGS10"], dates, LAG["DGS10"], 7)

    # ---- 트렌드캐치 원값
    vix_live = idx["vix"].reindex(dates)
    vix_fred, _ = asof(F["VIXCLS"], dates, 0, 7)
    col["tc_vix"] = vix_live.fillna(vix_fred)
    col["tc_hy"], obs["hy"] = asof(F["BAMLH0A0HYM2"], dates, LAG["BAMLH0A0HYM2"], 7)
    c = spy["Close"]
    col["tc_rsi"] = rsi14(c).reindex(dates)
    col["tc_dev"] = ((c / c.rolling(200).mean() - 1) * 100).reindex(dates)
    a200 = jload(os.path.join(DATA, "hist", "sp500_a200.json"), {})
    col["tc_a200"] = pd.Series({pd.Timestamp(k): v for k, v in a200.items()}, dtype=float).reindex(dates)
    manual = jload(os.path.join(DATA, "manual.json"), {})
    ms, mobs = manual_series(manual, dates)
    col["tc_fg"], col["tc_pc"], col["tc_aaii"], col["tc_margin"] = ms["fg"], ms["pc"], ms["aaii"], ms["margin"]
    obs.update({"fg": mobs["fg"], "pc": mobs["pc"], "aaii": mobs["aaii"], "margin": mobs["margin"]})
    for k in ("fg", "pc", "aaii", "margin"):
        col[f"obs_{k}"] = mobs[k].map(lambda x: x.strftime("%Y-%m-%d") if pd.notna(x) else None)


    # ---- 유동성 원값
    col["lq_fed"], obs["fed"] = pct_change_days(F["WALCL"], dates, 91, LAG["WALCL"], STALE["WALCL"])
    # 단위: WALCL·WTREGEN = 백만 달러, RRPONTSYD = 십억 달러 → 모두 십억 달러로
    nl = (F["WALCL"] / 1000).to_frame("w")
    tga = (F["WTREGEN"] / 1000).reindex(nl.index, method="ffill")
    rrp = F["RRPONTSYD"].reindex(nl.index, method="ffill")
    netliq = (nl["w"] - tga - rrp).dropna()
    col["lq_nl"], obs["nl"] = pct_change_days(netliq, dates, 91, 1, 16)
    col["lq_nl_level"], _ = asof(netliq, dates, 1, 16)
    col["lq_m2"], obs["m2"] = pct_change_days(F["M2SL"], dates, 365, LAG["M2SL"], STALE["M2SL"])
    e_now, obs["effr"] = asof(F["EFFR"], dates, 1, 7)
    e_past, _ = asof(F["EFFR"], dates - pd.Timedelta(days=91), 1)
    e_past.index = dates
    col["lq_effr"] = e_now - e_past
    col["lq_effr_level"] = e_now
    col["lq_hy"] = col["tc_hy"]
    obs["lq_hy"] = obs["hy"]
    dx = idx["dxy"]
    dpast, _ = asof(dx, dates - pd.Timedelta(days=182))
    dpast.index = dates
    col["lq_dxy"] = (col["dxy"] / dpast - 1) * 100
    col["lq_margin"] = col["tc_margin"]
    col["lq_bank"], obs["bank"] = pct_change_days(F["TOTBKCR"], dates, 365, LAG["TOTBKCR"], STALE["TOTBKCR"])
    v = vti["Volume"]
    col["lq_vol"] = (v / v.shift(1).rolling(20).mean() * 100).reindex(dates)
    col["lq_nfci"], obs["nfci"] = asof(F["NFCI"], dates, LAG["NFCI"], STALE["NFCI"])
    y_past, _ = asof(F["DGS10"], dates - pd.Timedelta(days=91), 1)
    y_past.index = dates
    col["lq_y10"] = col["us10y"]
    col["lq_y10_chg"] = (col["us10y"] - y_past) * 100

    # ---- 점수
    print("[2/4] 점수 계산", flush=True)
    for k, f in TC.items():
        col[f"s_tc_{k}"] = col[f"tc_{k}"].map(lambda x, f=f: f(x) if pd.notna(x) else np.nan)
    for k, f in LQ.items():
        if k == "y10":
            col["s_lq_y10"] = pd.Series([s_y10(a, b) for a, b in zip(col["lq_y10"], col["lq_y10_chg"])], index=dates, dtype=float)
        else:
            col[f"s_lq_{k}"] = col[f"lq_{k}"].map(lambda x, f=f: f(x) if pd.notna(x) else np.nan)
    # 종합 점수: data/weights.json 의 가중치 버전(적용 시작일별)을 따른다 — scripts/weights.py
    import weights as WM
    comp = WM.composite(pd.DataFrame({f"s_tc_{k}": col[f"s_tc_{k}"] for k in TC} | {f"s_lq_{k}": col[f"s_lq_{k}"] for k in LQ}, index=dates))
    col["tc_n"] = comp["tc_n"]
    col["tc"] = comp["tc"]
    col["lq_w"] = comp["lq_w"]
    col["lq"] = comp["lq"]

    df = pd.DataFrame(col, index=dates)
    return df, obs, {"spy_last": spy.index[-1], "naver_last": dates[-1]}


def series_json(df):
    prec = {"kospi": 2, "kospi_next": 2, "spx": 2, "ixic": 2, "dji": 2, "ndx": 2, "lq_nl_level": 0}
    cols = {}
    for k in df.columns:
        if k.startswith("obs_"):
            cols[k] = [v if isinstance(v, str) else None for v in df[k].values]
            continue
        n = prec.get(k, 3 if k.startswith(("lq_", "tc_", "us10y", "dxy", "vix")) else 2)
        cols[k] = [rnd(v, n) for v in df[k].values]
    return {"dates": [d.strftime("%Y-%m-%d") for d in df.index], "cols": cols}

# ---------------------------------------------------------------- 상관


def build_corr(df):
    print("[3/4] 지수 상관 계산", flush=True)
    wk = df.resample("W-FRI").last()
    out = {"zones_tc": ["공포", "불안", "중립", "과열", "광기"], "zones_lq": ["경색", "긴축", "중립", "우호", "풍부"]}
    idxmap = {"ndx": "ndx", "spx": "spx", "kospi": "kospi_next"}
    for comp, lab in [("tc", label_tc), ("lq", label_lq)]:
        out[comp] = {}
        sc = wk[comp]
        for name, colname in idxmap.items():
            px = wk[colname]
            res = {"buckets": {}, "ic": {}}
            for h in (1, 4, 12):
                fwd = (px.shift(-h) / px - 1) * 100
                d = pd.DataFrame({"s": sc, "f": fwd}).dropna()
                d["z"] = d["s"].map(lab)
                b = {}
                for z, g in d.groupby("z"):
                    b[z] = {"mean": rnd(g.f.mean(), 2), "win": rnd((g.f > 0).mean() * 100, 0), "n": int(len(g))}
                res["buckets"][str(h)] = b
                res["ic"][str(h)] = rnd(d.s.corr(d.f, method="spearman"), 3) if len(d) > 10 else None
            f4 = (px.shift(-4) / px - 1) * 100
            roll = sc.rolling(26, min_periods=20).corr(f4)
            res["rolling"] = {"dates": [x.strftime("%Y-%m-%d") for x in roll.index], "v": [rnd(x, 3) for x in roll.values]}
            out[comp][name] = res
    out["weeks"] = [x.strftime("%Y-%m-%d") for x in wk.index]
    return out

# ---------------------------------------------------------------- 현황판

SECTOR_KO = {"Technology": "기술", "Healthcare": "헬스케어", "Financial": "금융", "Consumer Defensive": "필수소비재",
             "Consumer Cyclical": "경기소비재", "Industrials": "산업재", "Utilities": "유틸리티",
             "Communication Services": "커뮤니케이션", "Real Estate": "부동산", "Basic Materials": "소재", "Energy": "에너지"}


def fnum(x):
    try:
        return float(str(x).replace("%", "").replace(",", ""))
    except Exception:
        return None


def build_board(date, df):
    print(f"[4/4] 현황판 {date:%Y-%m-%d} (finviz)", flush=True)
    allrows = finviz_screen("")
    chg = [fnum(r["Change"]) for r in allrows]
    nh = finviz_screen("ta_highlow52w_nh", order="-marketcap")
    nl_rows = finviz_screen("ta_highlow52w_nl")
    s50 = finviz_screen("ta_sma50_pa")
    s200 = finviz_screen("ta_sma200_pa")
    sp = finviz_screen("idx_sp500")
    sp200 = finviz_screen("idx_sp500,ta_sma200_pa")
    sp50 = finviz_screen("idx_sp500,ta_sma50_pa")
    n = len(allrows)
    breadth = {"universe": n, "adv": sum(1 for c in chg if c is not None and c > 0),
               "dec": sum(1 for c in chg if c is not None and c < 0), "nh": len(nh), "nl": len(nl_rows),
               "above50": rnd(len(s50) / n * 100, 1), "above200": rnd(len(s200) / n * 100, 1),
               "sp500_above200": rnd(len(sp200) / len(sp) * 100, 1), "sp500_above50": rnd(len(sp50) / len(sp) * 100, 1)}

    # 누적 기록
    key = date.strftime("%Y-%m-%d")
    bh_path = os.path.join(DATA, "hist", "breadth.json")
    bh = jload(bh_path, {})
    bh[key] = breadth
    jsave(bh_path, dict(sorted(bh.items())))
    a2_path = os.path.join(DATA, "hist", "sp500_a200.json")
    a2 = jload(a2_path, {})
    a2[key] = breadth["sp500_above200"]
    jsave(a2_path, dict(sorted(a2.items())))
    a5_path = os.path.join(DATA, "hist", "sp500_a50.json")  # 2017~ 과거값은 scripts/backfill_sp500_ma.py
    a5 = jload(a5_path, {})
    a5[key] = breadth["sp500_above50"]
    jsave(a5_path, dict(sorted(a5.items())))
    prev_keys = [k for k in sorted(bh) if k < key]
    prev = {"date": prev_keys[-1], **bh[prev_keys[-1]]} if prev_keys else None

    spset = {r["Ticker"] for r in sp}
    notes = jload(os.path.join(DATA, "notes", "companies.json"), {})
    def item(r):
        t = r["Ticker"]
        return {"t": t, "name": r["Company"], "sector": SECTOR_KO.get(r["Sector"], r["Sector"]), "ind": r["Industry"],
                "country": r["Country"], "mcap": fnum(r["Market Cap"]), "price": fnum(r["Price"]), "chg": fnum(r["Change"]),
                "sp": t in spset, "desc": (notes.get(t) or {}).get("desc")}
    # 섹터·산업 강도: 시총가중 등락률 (ETF·SPAC 제외)
    agg, iagg = {}, {}
    for r in allrows:
        c, m = fnum(r["Change"]), fnum(r["Market Cap"])
        if c is None or not m or r["Industry"] in ("Exchange Traded Fund", "Shell Companies"):
            continue
        for key2, store in ((SECTOR_KO.get(r["Sector"], r["Sector"]), agg), (r["Industry"], iagg)):
            a = store.setdefault(key2, {"w": 0.0, "wc": 0.0, "n": 0, "up": 0, "sec": SECTOR_KO.get(r["Sector"], r["Sector"]), "mem": []})
            a["w"] += m; a["wc"] += m * c; a["n"] += 1; a["up"] += c > 0
            if store is iagg:
                a["mem"].append((m, r["Ticker"], c))
    sector_perf = sorted([{"name": k, "chg": rnd(v["wc"] / v["w"], 2), "up_pct": rnd(v["up"] / v["n"] * 100, 0), "n": v["n"]}
                          for k, v in agg.items() if v["n"] >= 20], key=lambda x: -x["chg"])
    inds = [{"name": k, "sector": v["sec"], "chg": rnd(v["wc"] / v["w"], 2), "n": v["n"],
             "tops": [{"t": t, "chg": rnd(c, 2)} for _, t, c in sorted(v["mem"], reverse=True)[:3]]}
            for k, v in iagg.items() if v["n"] >= 8 and v["w"] >= 50000]
    inds.sort(key=lambda x: -x["chg"])
    # 강세주·약세주: S&P500 안에서
    sp_rows = [r for r in allrows if r["Ticker"] in spset and fnum(r["Change"]) is not None]
    gainers = [item(r) for r in sorted(sp_rows, key=lambda r: -fnum(r["Change"]))[:10]]
    losers = [item(r) for r in sorted(sp_rows, key=lambda r: fnum(r["Change"]))[:5]]
    mega = [item(r) for r in sorted(sp_rows, key=lambda r: -(fnum(r["Market Cap"]) or 0))[:10]]

    # 신고가: 특수증권 제외 → 시총 상위 40
    excl = {"preferred": [], "spac": 0, "etf": 0, "dup": []}
    clean, seen = [], {}
    for r in nh:
        name, ind = r["Company"], r["Industry"]
        if re.search(r"\bPRF\b|PERPETUAL|Preferred|Depositary Shares", name, re.I):
            excl["preferred"].append(r["Ticker"]); continue
        if ind == "Shell Companies":
            excl["spac"] += 1; continue
        if ind == "Exchange Traded Fund":
            excl["etf"] += 1; continue
        base = re.sub(r"\s+(Inc|Corp|Ltd|Co|Plc|Holdings?|Group|Class [A-C]|Series [A-Z]|-.*)\.?$", "", name, flags=re.I).strip().lower()
        if base in seen:
            excl["dup"].append(r["Ticker"]); continue
        seen[base] = r["Ticker"]
        clean.append(item(r))
    top = clean[:40]
    sec = {}
    for r in top:
        sec[r["sector"]] = sec.get(r["sector"], 0) + 1
    sectors = [{"name": k, "count": v, "pct": rnd(v / len(top) * 100, 1)} for k, v in sorted(sec.items(), key=lambda x: -x[1])]
    # 대표 신고가: S&P500 구성종목만, 당일 상승률 순 최대 9개 + 최근 3개월 종가
    feats = sorted([r for r in clean if r["sp"]], key=lambda r: -(r["chg"] or -99))[:9]
    for f in feats:
        try:
            q = finviz_quote(f["t"]).loc[:date]
            f["spark"] = [rnd(x, 2) for x in q["Close"].iloc[-63:].values]
            f["spark_from"] = f"{q.index[-min(63, len(q))]:%Y-%m-%d}"
        except Exception as e:  # 차트가 없어도 카드는 보여줌
            print(f"  ! {f['t']} 3개월 차트 실패: {e}")
        time.sleep(0.6)
    nh_list = [{"t": r["t"], "chg": r["chg"], "sp": r["sp"]} for r in clean]
    intraday = {"ndx": finviz_intraday("QQQ", date), "spx": finviz_intraday("SPY", date),
                "dji": finviz_intraday("DIA", date), "kospi": naver_kospi_intraday(date)}

    row = df.loc[date]
    def ix(k, n=2):
        s = df[k].dropna()
        s = s.loc[:date]
        if len(s) < 2:
            return None
        return {"close": rnd(s.iloc[-1], n), "chg": rnd((s.iloc[-1] / s.iloc[-2] - 1) * 100, 2),
                "spark": [rnd(x, n) for x in s.iloc[-6:].values]}
    y = df["us10y"].dropna().loc[:date]
    board = {
        "date": key, "generated": dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M KST"),
        "indices": {"spx": ix("spx"), "ixic": ix("ixic"), "dji": ix("dji"), "ndx": ix("ndx"), "kospi": ix("kospi"),
                    "vix": ix("vix"), "dxy": ix("dxy", 3),
                    "us10y": {"close": rnd(y.iloc[-1], 2), "chg_bp": rnd((y.iloc[-1] - y.iloc[-2]) * 100, 0),
                              "spark": [rnd(x, 2) for x in y.iloc[-6:].values], "obs_note": "FRED DGS10, 전일 기준"}},
        "breadth": breadth, "prev": prev, "nh_total": len(nh), "excluded": excl,
        "top40": top, "sectors": sectors, "features": feats, "nh_sp500": sum(1 for r in clean if r["sp"]), "nh_list": nh_list,
        "sector_perf": sector_perf, "ind_top": inds[:5], "ind_bottom": inds[-5:][::-1],
        "gainers": gainers, "losers": losers, "mega": mega, "intraday": intraday,
        "tc": rnd(row["tc"], 1), "lq": rnd(row["lq"], 1),
    }
    jsave(os.path.join(DATA, "board", f"{key}.json"), board)
    return board

# ---------------------------------------------------------------- 실행


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-board", action="store_true", help="finviz 현황판 생략")
    ap.add_argument("--force-board", action="store_true", help="이미 있어도 현황판 다시 생성")
    a = ap.parse_args()
    if not FINVIZ or not FRED_KEY:
        sys.exit("FINVIZ_AUTH, FRED_KEY 환경변수가 필요합니다")

    df, obs, info = build_series()
    last = df.index[-1]
    made_board = None
    if not a.no_board:
        bpath = os.path.join(DATA, "board", f"{last:%Y-%m-%d}.json")
        if info["spy_last"] != last:
            print(f"! finviz 날짜({info['spy_last']:%Y-%m-%d})와 지수 날짜({last:%Y-%m-%d})가 달라 현황판 생략")
        elif os.path.exists(bpath) and not a.force_board:
            print("현황판 이미 있음 — 생략 (--force-board 로 재생성)")
        else:
            made_board = build_board(last, df)
            # 오늘 S&P500 200일선 비율이 들어갔으니 점수 다시 계산
            df, obs, info = build_series()

    jsave(os.path.join(DATA, "series.json"), series_json(df))
    jsave(os.path.join(DATA, "corr.json"), build_corr(df))
    import wind  # 같은 폴더의 scripts/wind.py
    wnow = wind.build()
    print("풍향계", json.dumps(wnow, ensure_ascii=False))
    boards = sorted(f[:-5] for f in os.listdir(os.path.join(DATA, "board"))) if os.path.isdir(os.path.join(DATA, "board")) else []
    asof_map = {k: (v.iloc[-1].strftime("%Y-%m-%d") if pd.notna(v.iloc[-1]) else None) for k, v in obs.items()}
    jsave(os.path.join(DATA, "latest.json"), {
        "date": f"{last:%Y-%m-%d}", "boards": boards, "asof": asof_map,
        "generated": dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M KST")})
    r = df.iloc[-1]
    print(json.dumps({"date": f"{last:%Y-%m-%d}", "tc": rnd(r["tc"], 1), "tc_n": int(r["tc_n"]),
                      "lq": rnd(r["lq"], 1), "lq_w": rnd(r["lq_w"], 1), "board": bool(made_board)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
