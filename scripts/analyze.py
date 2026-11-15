#!/usr/bin/env python3
"""지표별 예측력(선행·후행) 분석 → data/analysis.json

각 지표의 주간 값(금요일 기준, 공개 지연 반영)과 S&P500·나스닥100 수익률의 관계를 본다.
- 이후 h주 순위상관(Spearman): 지표가 앞으로의 수익률을 얼마나 설명하는가 (선행성)
- 지난 13주 순위상관: 지표가 이미 지나간 수익률을 얼마나 반영하는가 (후행성)
- 시차 프로필: 지표 vs '4주 수익률이 끝나는 시점'을 −26주~+26주로 옮겨가며 본 상관
부호는 점수 방향에 맞춘다: +는 '점수가 높을수록(광기·풍부) 이후 수익률이 높았다', −는 그 반대.
겹치는 기간의 수익률이라 표본이 실제보다 많아 보이므로, 유효 표본(n/h)으로 신뢰 여부를 표시한다.
필요: FRED_KEY, FINVIZ_AUTH 환경변수
"""
import json, math, os, sys, datetime as dt
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import collect as C  # noqa: E402

START = "2010-07-09"
HS = [1, 4, 13, 26]
PROFILE = [-26, -13, -8, -4, 0, 4, 8, 13, 26]


def fred_long(sid, start="2000-01-01"):
    u = (f"https://api.stlouisfed.org/fred/series/observations?series_id={sid}"
         f"&api_key={C.FRED_KEY}&file_type=json&observation_start={start}")
    d = json.loads(C.http(u))
    return pd.Series({pd.Timestamp(o["date"]): float(o["value"]) for o in d["observations"] if o["value"] != "."}).sort_index()


def naver_long(code):
    end = (dt.date.today() + dt.timedelta(days=1)).strftime("%Y%m%d")
    d = json.loads(C.http(f"https://api.stock.naver.com/chart/foreign/index/{code}/day?startDateTime=199001010000&endDateTime={end}0000"))
    return pd.Series({pd.Timestamp(x["localDate"]): float(x["closePrice"]) for x in d}).sort_index()


def weekly(s):
    return s.resample("W-FRI").last()


def build_indicators():
    F = {k: fred_long(k) for k in ["WALCL", "WTREGEN", "RRPONTSYD", "M2SL", "EFFR", "BAMLH0A0HYM2", "TOTBKCR", "NFCI", "DGS10", "VIXCLS"]}
    spx = naver_long(".INX")
    dxy = naver_long(".DXY")
    ndx = fred_long("NASDAQ100", "2000-01-01")
    vti = C.finviz_quote("VTI")
    wk_dates = weekly(spx).loc[START:].index
    d = pd.DatetimeIndex(wk_dates)
    X = {}
    A = lambda s, lag, stale=9999: C.asof(s, d, lag, stale)[0]
    X["tc_vix"] = A(F["VIXCLS"], 0, 7)
    X["tc_hy"] = X["lq_hy"] = A(F["BAMLH0A0HYM2"], 1, 7)
    a200 = C.jload(os.path.join(C.DATA, "hist", "sp500_a200.json"), {})
    X["tc_a200"] = A(pd.Series({pd.Timestamp(k): v for k, v in a200.items()}).sort_index(), 0, 7)
    X["tc_rsi"] = A(C.rsi14(spx), 0, 7)
    X["tc_dev"] = A((spx / spx.rolling(200).mean() - 1) * 100, 0, 7)

    def chg(s, days, lag, stale):
        now = A(s, lag, stale); past = C.asof(s, d - pd.Timedelta(days=days), lag)[0]; past.index = d
        return now, past
    n, p = chg(F["WALCL"], 91, 1, 16); X["lq_fed"] = (n / p - 1) * 100
    nl = (F["WALCL"] / 1000).to_frame("w")
    netliq = (nl["w"] - (F["WTREGEN"] / 1000).reindex(nl.index, method="ffill") - F["RRPONTSYD"].reindex(nl.index, method="ffill").fillna(0)).dropna()
    n, p = chg(netliq, 91, 1, 16); X["lq_nl"] = (n / p - 1) * 100
    n, p = chg(F["M2SL"], 365, 55, 100); X["lq_m2"] = (n / p - 1) * 100
    n, p = chg(F["EFFR"], 91, 1, 7); X["lq_effr"] = n - p
    n, p = chg(dxy, 182, 0, 7); X["lq_dxy"] = (n / p - 1) * 100
    n, p = chg(F["TOTBKCR"], 365, 9, 21); X["lq_bank"] = (n / p - 1) * 100
    v = vti["Volume"]; X["lq_vol"] = A(v / v.shift(1).rolling(20).mean() * 100, 0, 7)
    X["lq_nfci"] = A(F["NFCI"], 5, 16)
    n, p = chg(F["DGS10"], 91, 1, 7); X["lq_y10"] = (n - p) * 100
    # 신용융자 YoY (YCharts/FINRA 월간, 2023-08~)
    ms, _ = C.manual_series(C.jload(os.path.join(C.DATA, "manual.json"), {}), d)
    X["tc_margin"] = X["lq_margin"] = ms["margin"]
    # 종합점수 (Seoks 시계열, 2023~)
    s = C.jload(os.path.join(C.DATA, "series.json"), None)
    if s:
        sd = pd.DatetimeIndex(s["dates"])
        for k in ("tc", "lq"):
            X[k] = A(pd.Series(s["cols"][k], index=sd, dtype=float), 0, 7)
    px = {"spx": weekly(spx).reindex(d), "ndx": weekly(ndx).reindex(d)}
    return pd.DataFrame(X, index=d), px


# 점수 방향: +1 = 값이 클수록 점수가 높음
DIR = {"tc_margin": 1, "lq_margin": 1, "tc_vix": -1, "tc_hy": -1, "tc_a200": 1, "tc_rsi": 1, "tc_dev": 1, "tc": 1,
       "lq_fed": 1, "lq_nl": 1, "lq_m2": 1, "lq_effr": -1, "lq_hy": -1, "lq_dxy": -1, "lq_bank": 1, "lq_vol": 1, "lq_nfci": -1, "lq_y10": -1, "lq": 1}
NA = {"fg": "CNN 공포탐욕 과거 일별 자료를 자동으로 받을 수 없음 (매일 쌓이면 분석에 포함)",
      "aaii": "AAII 과거 주간 자료는 유료 회원 전용 (매주 쌓이면 분석에 포함)",
      "pc": "Cboe 풋콜 과거 일별 자료를 자동으로 받을 수 없음 (매일 쌓이면 분석에 포함)"}


def sp(a, b):
    m = pd.concat([a, b], axis=1).dropna()
    if len(m) < 30:
        return None, len(m)
    return float(m.iloc[:, 0].corr(m.iloc[:, 1], method="spearman")), len(m)


def analyze_one(x, px, sign):
    lp = np.log(px)
    out = {"ic": {}, "sig": {}, "n": {}}
    for h in HS:
        f = lp.shift(-h) - lp
        r, n = sp(x, f)
        out["ic"][str(h)] = None if r is None else round(r * sign, 3)
        out["n"][str(h)] = n
        thr = 2 / math.sqrt(max(n / h, 1))
        out["sig"][str(h)] = bool(r is not None and abs(r) > thr)
    past = lp - lp.shift(13)
    r, _ = sp(x, past)
    out["past13"] = None if r is None else round(r * sign, 3)
    r4 = lp - lp.shift(4)
    prof = []
    for k in PROFILE:
        r, _ = sp(x, r4.shift(-k))
        prof.append(None if r is None else round(r * sign, 3))
    out["profile"] = prof
    f13 = lp.shift(-13) - lp
    m = pd.concat([x, f13], axis=1).dropna()
    half = len(m) // 2
    if half > 30:
        a = m.iloc[:half]; b = m.iloc[half:]
        out["half"] = [round(float(a.iloc[:, 0].corr(a.iloc[:, 1], method="spearman")) * sign, 3),
                       round(float(b.iloc[:, 0].corr(b.iloc[:, 1], method="spearman")) * sign, 3)]
    else:
        out["half"] = None
    xs = x.dropna()
    out["start"] = xs.index[0].strftime("%Y-%m-%d") if len(xs) else None
    out["weeks"] = int(len(xs))
    # 판정
    lead = max(abs(out["ic"]["4"] or 0), abs(out["ic"]["13"] or 0))
    lag = abs(out["past13"] or 0)
    lead_ic = out["ic"]["13"] if abs(out["ic"]["13"] or 0) >= abs(out["ic"]["4"] or 0) else out["ic"]["4"]
    direc = "" if lead_ic is None else ("점수 높을 때 이후 수익률 ↑" if lead_ic > 0 else "점수 높을 때 이후 수익률 ↓")
    stable = out["half"] is not None and out["half"][0] * out["half"][1] > 0
    strong = any(abs(out["ic"][h] or 0) >= 0.15 and out["sig"][h] for h in ("4", "13"))
    if strong:
        role = "선행 (뚜렷)"
    elif lead >= 0.08:
        role = "선행 (약함)"
    elif lag >= 0.3:
        role = "후행"
    else:
        role = "관계 약함"
    if role.startswith("선행") and lag >= 0.3:
        role += " · 후행"
    if out["weeks"] < 300:
        role += f" · 표본 {out['weeks'] / 52:.0f}년"
    out["role"] = role
    out["direction"] = direc
    out["stable"] = stable
    return out


def main():
    if not C.FRED_KEY or not C.FINVIZ:
        sys.exit("FRED_KEY, FINVIZ_AUTH 환경변수가 필요합니다")
    X, px = build_indicators()
    res = {"generated": dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M KST"),
           "start": START, "end": X.index[-1].strftime("%Y-%m-%d"), "hs": HS, "profile_k": PROFILE, "na": NA, "items": {}}
    for k in X.columns:
        res["items"][k] = {ix: analyze_one(X[k], px[ix], DIR[k]) for ix in ("spx", "ndx")}
        r = res["items"][k]["spx"]
        print(f"{k:10s} {r['start']} w={r['weeks']:4d} IC4={r['ic']['4']} IC13={r['ic']['13']} past13={r['past13']} {r['role']} {r['direction']}")
    C.jsave(os.path.join(C.DATA, "analysis.json"), res)


if __name__ == "__main__":
    main()
