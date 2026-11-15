"""증시 풍향계: 트렌드캐치(거꾸로)와 유동성을 0~100 하나의 숫자로.

풍향계 = 60% × 심리 바람 + 40% × 유동성 바람
  심리 바람   = (5 − 트렌드캐치) ÷ 4 × 100   공포일수록 높음 (역발상)
  유동성 바람 = (유동성 − 1) ÷ 4 × 100        돈이 넉넉할수록 높음
→ 정리하면 65 − 15 × 트렌드캐치 + 10 × 유동성 (사분면 '기회' 모서리 100, '위험' 모서리 0)

매일 data/series.json을 읽어 data/wind.json을 만든다:
  값 이력, 구간별 이후 수익률, 지수 대비 선행·후행 순위상관, 검증이 쌓이는 모습(누적 상관)
"""
import json
import os
import sys

import numpy as np
import pandas as pd

DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
W_SENT, W_LIQ = 0.6, 0.4
ZONES = [  # (하한, 이름, 행동 힌트, 색)
    (0, "강한 역풍", "매우 조심", "#ef4444"),
    (30, "역풍", "조심", "#f59e6b"),
    (45, "무풍", "관망", "#94a3b8"),
    (55, "순풍", "우호", "#5fd3b0"),
    (70, "강한 순풍", "적극", "#22c55e"),
]
HS = [5, 10, 20, 40, 60]          # 거래일: 1주·2주·1개월·2개월·3개월
HNAME = {5: "1주", 10: "2주", 20: "1개월", 40: "2개월", 60: "3개월"}


def zone_of(v):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return None
    z = ZONES[0]
    for zz in ZONES:
        if v >= zz[0]:
            z = zz
    return z[1]


def rnd(x, n=1):
    return None if x is None or (isinstance(x, float) and np.isnan(x)) else round(float(x), n)


def spearman(a, b):
    m = a.notna() & b.notna()
    if m.sum() < 30:
        return None, int(m.sum())
    return rnd(a[m].corr(b[m], method="spearman"), 3), int(m.sum())


def build(series_path=None, out_path=None):
    series_path = series_path or os.path.join(DATA, "series.json")
    out_path = out_path or os.path.join(DATA, "wind.json")
    s = json.load(open(series_path, encoding="utf-8"))
    df = pd.DataFrame(s["cols"], index=pd.to_datetime(s["dates"]))
    tc, lq = df["tc"].astype(float), df["lq"].astype(float)
    sent = (5 - tc) / 4 * 100
    liq = (lq - 1) / 4 * 100
    w = (W_SENT * sent + W_LIQ * liq).clip(0, 100)
    start = w.first_valid_index()

    out = {"formula": "65 − 15 × 트렌드캐치 + 10 × 유동성", "weights": {"sent": W_SENT, "liq": W_LIQ},
           "zones": [{"from": z[0], "name": z[1], "act": z[2], "color": z[3]} for z in ZONES],
           "start": f"{start:%Y-%m-%d}", "end": f"{df.index[-1]:%Y-%m-%d}",
           "dates": [f"{d:%Y-%m-%d}" for d in df.index],
           "w": [rnd(x) for x in w.values], "sent": [rnd(x) for x in sent.values], "liq": [rnd(x) for x in liq.values]}

    d = pd.DataFrame({"w": w}).loc[start:]
    stats, lead, track = {}, {}, {}
    for ix in ("spx", "ndx"):
        px = df[ix].astype(float).loc[start:]
        fwd = {h: px.shift(-h) / px - 1 for h in HS}
        past = {h: px / px.shift(h) - 1 for h in HS}
        lead[ix] = {"fwd": {}, "past": {}, "n": {}}
        for h in HS:
            ic, n = spearman(d["w"], fwd[h])
            lead[ix]["fwd"][str(h)] = ic
            lead[ix]["n"][str(h)] = n
            lead[ix]["past"][str(h)] = spearman(d["w"], past[h])[0]
        # 구간별 이후 1개월·3개월
        z = d["w"].map(zone_of)
        stats[ix] = {}
        for h in (20, 60):
            r = {}
            for zz in ZONES:
                m = (z == zz[1]) & fwd[h].notna()
                if m.sum():
                    v = fwd[h][m] * 100
                    r[zz[1]] = {"n": int(m.sum()), "mean": rnd(v.mean(), 2), "win": rnd((v > 0).mean() * 100, 0)}
            m = fwd[h].notna()
            r["전체"] = {"n": int(m.sum()), "mean": rnd(fwd[h][m].mean() * 100, 2), "win": rnd((fwd[h][m] > 0).mean() * 100, 0)}
            stats[ix][str(h)] = r
        # 검증이 쌓이는 모습: 매월 말, 그때까지 결과가 확정된 쌍만으로 계산한 누적 순위상관
        ends = d.index.to_series().groupby(d.index.to_period("M")).max().values
        tr = {"dates": [], "20": [], "60": []}
        for e in ends:
            tr["dates"].append(f"{pd.Timestamp(e):%Y-%m-%d}")
            for h in (20, 60):
                # t+h 거래일이 e 이하인 t만
                pos = d.index.get_loc(pd.Timestamp(e))
                cut = d.index[: max(0, pos - h + 1)]
                ic, n = spearman(d["w"].loc[cut], fwd[h].loc[cut]) if len(cut) else (None, 0)
                tr[str(h)].append(ic if n >= 60 else None)
        track[ix] = tr
    out.update({"stats": stats, "lead": lead, "track": track, "hname": {str(k): v for k, v in HNAME.items()}})

    # 사분면별 이후 3개월 (트렌드캐치 탭·풍향계 탭 판단 보조용)
    q = pd.DataFrame({"tc": tc, "lq": lq}).loc[start:]
    px = df["spx"].astype(float).loc[start:]
    f60 = (px.shift(-60) / px - 1) * 100
    def quad(r):
        if pd.isna(r.tc) or pd.isna(r.lq):
            return None
        return ("과열 주의" if r.tc >= 3 else "기회") if r.lq >= 3 else ("위험" if r.tc >= 3 else "바닥 탐색")
    qq = q.apply(quad, axis=1)
    out["quad"] = {}
    for nm in ("기회", "과열 주의", "위험", "바닥 탐색"):
        m = (qq == nm) & f60.notna()
        out["quad"][nm] = {"n": int(m.sum()), "mean": rnd(f60[m].mean(), 2) if m.sum() else None,
                           "win": rnd((f60[m] > 0).mean() * 100, 0) if m.sum() else None}

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
    last = w.dropna()
    return {"date": f"{last.index[-1]:%Y-%m-%d}", "wind": rnd(last.iloc[-1]), "zone": zone_of(last.iloc[-1])}


if __name__ == "__main__":
    print(json.dumps(build(*sys.argv[1:3]), ensure_ascii=False))
