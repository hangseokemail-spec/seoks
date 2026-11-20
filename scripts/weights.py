"""점수 가중치 (트렌드캐치 9지표 · 유동성 11지표 · 풍향계 심리/유동성) — data/weights.json 하나에서 읽는다.

- 가중치는 '버전'으로 쌓인다. 각 버전은 적용 시작일(from)이 있고, 그날부터 다음 버전 전날까지의 점수에 쓰인다.
  → 이미 발표한 날의 점수·코멘트는 바뀌지 않는다(그날 쓰던 가중치 그대로).
- 매주 토요일 점검해 새 버전을 더한다(scripts/weights_eval.py, WEIGHTS.md). 새 팩터를 넣거나 빼면 버전마다 지표 목록이 달라진다.
"""
import json
import os

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(ROOT, "data", "weights.json")

TC_KEYS = ["fg", "aaii", "vix", "hy", "pc", "margin", "a200", "rsi", "dev"]
LQ_KEYS = ["fed", "nl", "m2", "effr", "hy", "dxy", "margin", "bank", "vol", "nfci", "y10"]
TC_MIN_N = 5        # 트렌드캐치: 값이 있는 지표가 5개 이상일 때만
LQ_MIN_W = 70       # 유동성: 값이 있는 지표 가중치 합이 70% 이상일 때만


def load(path=PATH):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def keys_of(v, grp):
    """버전(또는 후보)에 들어 있는 지표 키 — 원래 지표는 정해진 순서, 새 팩터는 그 뒤."""
    base = TC_KEYS if grp == "tc" else LQ_KEYS
    d = v[grp]
    return [k for k in base if k in d] + [k for k in d if k not in base]


def norm(d, keys=None):
    keys = keys if keys is not None else list(d)
    tot = sum(float(d.get(k, 0)) for k in keys)
    return {k: float(d.get(k, 0)) / tot * 100 for k in keys}


def current(W=None):
    W = W or load()
    return W["versions"][-1]


def version_index(dates, W=None):
    """날짜마다 몇 번째 버전을 쓰는지 (0부터)."""
    W = W or load()
    idx = pd.to_datetime(pd.Index(dates))
    out = np.zeros(len(idx), dtype=int)
    for k, v in enumerate(W["versions"]):
        out[idx >= pd.Timestamp(v["from"])] = k
    return out


def rnd1(x):
    """소수 첫째 자리 반올림(기존과 같은 numpy 방식). 계산 환경마다 3.15가 3.1/3.2로 갈리지 않게 먼저 9자리에서 정리한다."""
    return np.round(np.round(x.astype(float), 9), 1)


def composite(scores, ver=None, W=None):
    """scores: DataFrame(index=날짜, 열 s_tc_*, s_lq_*). ver: 날짜별로 쓸 버전 dict(없으면 버전 이력대로).
    반환: DataFrame(tc, tc_n, lq, lq_w)."""
    W = W or load()
    dates = scores.index
    col = lambda grp, k: scores[f"s_{grp}_{k}"].astype(float) if f"s_{grp}_{k}" in scores else pd.Series(np.nan, index=dates)
    vers = [ver] if ver is not None else W["versions"]
    vi = np.zeros(len(dates), dtype=int) if ver is not None else version_index(dates, W)
    tc = pd.Series(np.nan, index=dates)
    lq = pd.Series(np.nan, index=dates)
    lqw = pd.Series(np.nan, index=dates)
    tcn = pd.Series(0, index=dates)
    for k, v in enumerate(vers):
        m = vi == k
        if not m.any():
            continue
        # 버전마다 들어 있는 지표가 다를 수 있다(새 팩터 추가·빼기). 지표 목록 = 그 버전의 가중치 키
        tk, lk = keys_of(v, "tc"), keys_of(v, "lq")
        tcs = pd.DataFrame({x: col("tc", x) for x in tk}, index=dates)
        lqs = pd.DataFrame({x: col("lq", x) for x in lk}, index=dates)
        tcn[m] = tcs[m].notna().sum(axis=1)
        # 원래 계산 순서를 그대로 따른다(반올림 경계에서 값이 달라지지 않게): 같은 비중이면 단순평균, 아니면 원 가중치로 가중평균
        wt = pd.Series({x: float(v["tc"][x]) for x in tk})
        wl = pd.Series({x: float(v["lq"][x]) for x in lk})
        a, b = tcs[m], lqs[m]
        if wt.nunique() == 1:
            tc[m] = rnd1(a.mean(axis=1))
        else:
            aw = a.notna().mul(wt, axis=1).sum(axis=1)
            tc[m] = rnd1(a.fillna(0).mul(wt, axis=1).sum(axis=1) / aw.replace(0, np.nan))
        bw = b.notna().mul(wl, axis=1).sum(axis=1)
        lqw[m] = bw / wl.sum() * 100
        lq[m] = rnd1(b.fillna(0).mul(wl, axis=1).sum(axis=1) / bw.replace(0, np.nan))
    tc = tc.where(tcn >= TC_MIN_N)
    lq = lq.where(lqw >= LQ_MIN_W)
    return pd.DataFrame({"tc": tc, "tc_n": tcn, "lq": lq, "lq_w": lqw.round(2)})


def wind_parts(tc, lq, dates=None, ver=None, W=None):
    """풍향계 = 심리비중 × (5 − 트렌드캐치)/4×100 + 유동성비중 × (유동성 − 1)/4×100"""
    W = W or load()
    sent = (5 - tc) / 4 * 100
    liq = (lq - 1) / 4 * 100
    if ver is not None:
        ws = pd.Series(ver["wind"]["sent"], index=tc.index)
    else:
        vi = version_index(tc.index if dates is None else dates, W)
        ws = pd.Series([W["versions"][k]["wind"]["sent"] for k in vi], index=tc.index)
    w = (ws * sent + (1 - ws) * liq).clip(0, 100)
    return w, sent, liq, ws


def formula(v):
    """버전의 풍향계 식을 'a − b × 트렌드캐치 + c × 유동성' 꼴로."""
    s = float(v["wind"]["sent"]); l = 1 - s
    a, b, c = 125 * s - 25 * l, 25 * s, 25 * l
    f = lambda x: f"{x:.2f}".rstrip("0").rstrip(".")
    return f"{f(a)} − {f(b)} × 트렌드캐치 + {f(c)} × 유동성", (a, b, c)
