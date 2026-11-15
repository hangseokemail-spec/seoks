"""S&P500 50일선·200일선 위 종목 비율 과거값을 구성종목 일봉으로 직접 계산한다 (한 번만 돌리는 보충용).

FINVIZ_AUTH=... python3 scripts/backfill_sp500_ma.py
  - 현재 S&P500 구성종목 목록(finviz 스크리너) → 종목별 일봉(quote_export p=d, 약 10년)
  - 종목당 1초 이상 쉬어 finviz 차단을 피한다. 받은 일봉은 data/raw/closes/ 에 저장(커밋 안 됨)해 다시 돌릴 때 재사용
  - 날짜별: 종가 > 50일 이동평균인 종목 수 ÷ 50일 평균을 낼 수 있는 종목 수 × 100
  - 결과: data/hist/sp500_a50.json (2017-08 이후). 200일선도 같은 방법으로 계산해 기존 sp500_a200.json과 비교만 함
한계: 지금 구성종목 기준이라 과거에 편입·제외된 종목은 반영되지 않는다(생존 편향). 기존 200일선 과거값과 같은 방식.
"""
import json
import os
import sys
import time

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import collect  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "data", "raw", "closes")
HIST = os.path.join(ROOT, "data", "hist")


def main():
    os.makedirs(RAW, exist_ok=True)
    sp = collect.finviz_screen("idx_sp500")
    tickers = sorted({r["Ticker"] for r in sp})
    print("S&P500", len(tickers), "종목", flush=True)
    closes = {}
    for n, t in enumerate(tickers, 1):
        p = os.path.join(RAW, f"{t}.csv")
        if os.path.exists(p):
            s = pd.read_csv(p, index_col=0, parse_dates=True).iloc[:, 0]
        else:
            try:
                df = collect.finviz_quote(t)
                s = df["Close"]
                s.to_frame("Close").to_csv(p)
            except Exception as e:  # noqa
                print("! 실패", t, e, flush=True)
                time.sleep(5)
                continue
            time.sleep(1.1)
        closes[t] = s
        if n % 50 == 0:
            print(f"{n}/{len(tickers)}", flush=True)
    px = pd.DataFrame(closes).sort_index()
    out = {}
    for w in (50, 200):
        ma = px.rolling(w, min_periods=w).mean()
        valid = ma.notna() & px.notna()
        above = (px > ma) & valid
        pct = (above.sum(axis=1) / valid.sum(axis=1) * 100).where(valid.sum(axis=1) >= 300)
        out[w] = pct.dropna().round(1)
    a200_old = collect.jload(os.path.join(HIST, "sp500_a200.json"), {})
    start = min(a200_old) if a200_old else "2017-08-18"
    a50 = {d.strftime("%Y-%m-%d"): float(v) for d, v in out[50].items() if d.strftime("%Y-%m-%d") >= start}
    # 기존 파일에 있는 최근 실측값(finviz 스크리너 기준)은 그대로 둔다
    old50 = collect.jload(os.path.join(HIST, "sp500_a50.json"), {})
    a50.update(old50)
    bh = collect.jload(os.path.join(HIST, "breadth.json"), {})
    for d, r in bh.items():
        if r.get("sp500_above50") is not None:
            a50[d] = r["sp500_above50"]
    collect.jsave(os.path.join(HIST, "sp500_a50.json"), dict(sorted(a50.items())))
    # 검증: 같은 방법의 200일선 값과 기존 파일 비교
    cmp = [(a200_old[d], float(out[200].get(pd.Timestamp(d), float("nan")))) for d in a200_old if pd.Timestamp(d) in out[200].index]
    if cmp:
        diff = [abs(a - b) for a, b in cmp]
        print(json.dumps({"검증_200일선_비교일수": len(cmp), "평균차이%p": round(sum(diff) / len(diff), 2), "최대차이%p": round(max(diff), 1)}, ensure_ascii=False))
    print(json.dumps({"sp500_a50": len(a50), "start": min(a50), "end": max(a50), "last": a50[max(a50)]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
