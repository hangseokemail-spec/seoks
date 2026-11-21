"""팩터 원자료 받기 — 정확한 숫자를 주는 출처만 씁니다.

출처(다리, leg) 종류:
  {"src": "fred", "id": "VIXCLS"}            FRED 시리즈. 열쇠(FRED_KEY)가 있으면 API, 없으면 공개 CSV(fredgraph).
  {"src": "naver", "fut": "GCcv1"}            네이버 해외 선물 연결물 일별 종가(최근 약 3년).
                                               3년보다 앞은 같은 상품의 ETF 일별 종가(2010-07~)를 '겹치는 첫 1년의 비율 중앙값'으로
                                               선물 수준에 맞춰 잇습니다(과거 시험용). 받은 선물 값은 파일에 쌓아 두고 지우지 않습니다.
  {"src": "naver_index", "code": ".INX"}      네이버 해외 지수 일별 종가(2010-07~).
  {"src": "csv", "url": "...", "col": "ebp"}  공개 CSV 한 열(예: 연준 초과 채권 프리미엄 EBP).
계산(calc):
  vrp         변동성 위험 프리미엄 = VIX² − (S&P500 최근 22거래일 일간 로그수익률(%) 제곱합 × 252/22)   (Bollerslev·Tauchen·Zhou 2009)
  output_gap  산출 갭 = log 산업생산 − 그달까지 자료로만 맞춘 2차 추세(%)   (Cooper·Priestley 2009)

모든 함수는 (pandas Series[날짜→값], 상태 dict)를 돌려줍니다. 상태는 다음에 이어 받기 위해 원자료 파일에 그대로 저장합니다.
"""
import csv
import datetime as dt
import io
import json
import os
import time
import urllib.request

import numpy as np
import pandas as pd

UA = {"User-Agent": "Mozilla/5.0 (seoks factor fetch)"}
START = "2000-01-01"

# 선물 → 과거를 이을 ETF (네이버 코드). 원유는 ETF(USO)가 월물 교체 손실로 유가와 크게 달라 잇지 않고 FRED 현물을 씁니다.
NAVER_ETF = {"GCcv1": "GLD", "SIcv1": "SLV", "PLcv1": "PPLT.K", "HGcv1": "CPER.K", "PAcv1": "PALL.K"}
NAVER_CAT = {"GCcv1": "metals", "SIcv1": "metals", "PLcv1": "metals", "HGcv1": "metals", "PAcv1": "metals",
             "CLcv1": "energy", "NGcv1": "energy"}
NAME = {"GCcv1": "금 선물", "SIcv1": "은 선물", "PLcv1": "백금 선물", "HGcv1": "구리 선물", "PAcv1": "팔라듐 선물",
        "CLcv1": "WTI 원유 선물", "NGcv1": "천연가스 선물"}


def http(url, timeout=60, tries=3):
    last = None
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
                return r.read()
        except Exception as ex:  # noqa: BLE001
            last = ex
            time.sleep(2 * (i + 1))
    raise last


def _num(x):
    return float(str(x).replace(",", ""))


def _ser(d):
    return pd.Series({pd.Timestamp(k): float(v) for k, v in d.items()}).sort_index() if d else pd.Series(dtype=float)


def _dict(s, nd=6):
    return {f"{k:%Y-%m-%d}": round(float(v), nd) for k, v in s.dropna().items()}


# ---------------------------------------------------------------- FRED
def fred(sid, start=START):
    key = os.environ.get("FRED_KEY", "").strip()
    if key:
        d = json.loads(http(f"https://api.stlouisfed.org/fred/series/observations?series_id={sid}"
                            f"&api_key={key}&file_type=json&observation_start={start}"))
        return _ser({o["date"]: o["value"] for o in d["observations"] if o["value"] not in (".", "")})
    txt = http(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}&cosd={start}").decode()
    rows = list(csv.reader(io.StringIO(txt)))
    if not rows or len(rows[0]) < 2:
        raise RuntimeError(f"FRED {sid}: CSV 형식이 아님")
    return _ser({r[0]: r[1] for r in rows[1:] if len(r) > 1 and r[1] not in (".", "")})


# ---------------------------------------------------------------- 네이버
def naver_fut_pages(code, max_pages=40):
    """해외 선물 연결물 일별 종가. 한 쪽 60개, 최근부터. 반환: Series(거래일 → 종가)."""
    cat = NAVER_CAT.get(code, "metals")
    out = {}
    for p in range(1, max_pages + 1):
        d = json.loads(http(f"https://api.stock.naver.com/marketindex/{cat}/{code}/prices?page={p}&pageSize=60"))
        if not d:
            break
        for x in d:
            out[x["localTradedAt"][:10]] = _num(x["closePrice"])
        if len(d) < 60:
            break
    return _ser(out)


def naver_chart(kind, code):
    """kind: 'item'(해외 종목·ETF) 또는 'index'(해외 지수). 2010-07부터 일별 종가."""
    end = (dt.date.today() + dt.timedelta(days=1)).strftime("%Y%m%d")
    d = json.loads(http(f"https://api.stock.naver.com/chart/foreign/{kind}/{code}/day?startDateTime=199901010000&endDateTime={end}0000"))
    return _ser({f"{x['localDate'][:4]}-{x['localDate'][4:6]}-{x['localDate'][6:]}": x["closePrice"] for x in d})


def naver_leg(code, old=None, full=False):
    """선물 값은 쌓아 두고(old['fut']), 앞부분은 ETF를 비율로 맞춰 잇는다. 반환 (합친 Series, 상태)."""
    old = old or {}
    fut_old = _ser(old.get("fut"))
    pages = 40 if (full or len(fut_old) < 500) else 2
    fut_new = naver_fut_pages(code, pages)
    fut = pd.concat([fut_old, fut_new])
    fut = fut[~fut.index.duplicated(keep="last")].sort_index()
    st = {"fut": _dict(fut), "fut_code": code, "fut_name": NAME.get(code, code)}
    etf_code = old.get("etf_code") or NAVER_ETF.get(code)
    hist = pd.Series(dtype=float)
    if etf_code:
        if old.get("etf_scaled"):
            hist = _ser(old["etf_scaled"])
            st.update({k: old[k] for k in ("etf_code", "etf_scale", "etf_scale_window") if k in old})
        else:
            etf = naver_chart("item", etf_code)
            j = pd.concat([fut, etf], axis=1, join="inner").dropna()
            j = j[j.index < j.index[0] + pd.Timedelta(days=365)]          # 겹치는 첫 1년
            if len(j) >= 120:
                scale = float((j.iloc[:, 0] / j.iloc[:, 1]).median())
                hist = (etf[etf.index < fut.index[0]] * scale)
                st.update({"etf_code": etf_code, "etf_scale": round(scale, 6),
                           "etf_scale_window": f"{j.index[0]:%Y-%m-%d}~{j.index[-1]:%Y-%m-%d}"})
        st["etf_scaled"] = _dict(hist)
    comb = pd.concat([hist[hist.index < fut.index[0]] if len(fut) else hist, fut]).sort_index()
    return comb, st


def naver_index_leg(code, old=None):
    old = old or {}
    s_old = _ser(old.get("v"))
    s = pd.concat([s_old, naver_chart("index", code)])
    s = s[~s.index.duplicated(keep="last")].sort_index()
    return s, {"v": _dict(s, 4), "code": code}


# ---------------------------------------------------------------- CSV
def csv_leg(url, col, date_col=None):
    txt = http(url).decode("utf-8-sig")
    rows = list(csv.DictReader(io.StringIO(txt)))
    if not rows:
        raise RuntimeError("CSV 비어 있음")
    dc = date_col or list(rows[0].keys())[0]
    return _ser({r[dc][:10]: r[col] for r in rows if r.get(col) not in (None, "", ".", "NA")}), {}


# ---------------------------------------------------------------- 다리 하나
def leg(spec, old=None):
    s = spec.get("src")
    if s == "fred":
        return fred(spec["id"], spec.get("start", START)), {}
    if s == "naver":
        return naver_leg(spec["fut"], old)
    if s == "naver_index":
        return naver_index_leg(spec["code"], old)
    if s == "csv":
        return csv_leg(spec["url"], spec["col"], spec.get("date_col"))
    raise ValueError(f"모르는 출처 {s}")


def leg_name(spec):
    s = spec.get("src")
    return {"fred": lambda: f"FRED {spec['id']}", "naver": lambda: f"네이버 {NAME.get(spec['fut'], spec['fut'])}",
            "naver_index": lambda: f"네이버 {spec['code']}", "csv": lambda: spec.get("name") or spec["url"]}[s]()


# ---------------------------------------------------------------- 계산
def vrp_from(spx, vix):
    """VRP = VIX² − 실현분산(S&P500 최근 22거래일 일간 로그수익률(%) 제곱합 × 252/22, %²)."""
    lr = np.log(spx).diff() * 100
    rv = (lr ** 2).rolling(22, min_periods=22).sum() * 252 / 22
    j = pd.concat([vix ** 2, rv], axis=1, join="inner").dropna()
    return j.iloc[:, 0] - j.iloc[:, 1]


def output_gap_from(ip, fit_start="1960-01-01", first="1975-01-01"):
    """산출 갭(Cooper·Priestley 2009): log 산업생산 − 2차 추세. 추세는 매달 '그달까지의 자료로만' 다시 맞춘다(미리 보기 없음)."""
    y = np.log(ip[ip.index >= pd.Timestamp(fit_start)].dropna())
    t = np.arange(len(y), dtype=float)
    out = {}
    for i in range(len(y)):
        if y.index[i] < pd.Timestamp(first) or i < 120:
            continue
        c = np.polyfit(t[:i + 1], y.values[:i + 1], 2)
        out[y.index[i]] = float((y.values[i] - np.polyval(c, t[i])) * 100)
    return pd.Series(out).sort_index()


# 계산 팩터: 이름 → (필요한 다리들, 계산 함수)
CALC_LEGS = {
    "vrp": ([{"src": "naver_index", "code": ".INX"}, {"src": "fred", "id": "VIXCLS"}], lambda spx, vix: vrp_from(spx, vix)),
    "output_gap": ([{"src": "fred", "id": "INDPRO", "start": "1950-01-01"}], lambda ip: output_gap_from(ip)),
}
CALC_DESC = {"vrp": "VIX(FRED VIXCLS)² − S&P500(네이버 .INX) 22거래일 실현분산",
             "output_gap": "FRED 산업생산(INDPRO) log − 그달까지 자료로 맞춘 2차 추세(%)"}


def calc(name, old=None):
    old = old or {}
    legs, fn = CALC_LEGS[name]
    vals, st = [], {}
    for i, spec in enumerate(legs):
        v, s_ = leg(spec, old.get(str(i)))
        vals.append(v)
        if s_:
            st[str(i)] = s_
    return fn(*vals), st


CALCS = {k: (lambda old=None, _k=k: calc(_k, old)) for k in CALC_LEGS}


def combine(src, old=None):
    """factors.json의 source(type mix·calc)를 받아 (값 Series, 상태)를 만든다.
    mix: {"type":"mix", "num": 다리, "den": 다리(없으면 num 그대로)}"""
    old = old or {}
    if src["type"] == "calc":
        v, st = CALCS[src["name"]](old.get("calc"))
        return v, {"calc": st}
    a, sa = leg(src["num"], (old.get("legs") or {}).get("num"))
    st = {"legs": {"num": sa}}
    if not src.get("den"):
        return a, st
    b, sb = leg(src["den"], (old.get("legs") or {}).get("den"))
    st["legs"]["den"] = sb
    return ratio(a, b), st


def ratio(a, b):
    """서로 다른 시장의 날짜는 '그날까지의 마지막 값'으로 맞춘다(앞으로 채우기 최대 5일)."""
    idx = a.index.union(b.index)
    A = a.reindex(idx).ffill(limit=5)
    B = b.reindex(idx).ffill(limit=5)
    r = (A / B).dropna()
    return r[r.index >= max(a.index[0], b.index[0])]


def describe(src):
    if src["type"] == "calc":
        return CALC_DESC[src["name"]]
    n = leg_name(src["num"])
    return f"{n} ÷ {leg_name(src['den'])}" if src.get("den") else n
