"""팩터 시험실 — 팩터 도서관(data/factor_library.json)의 후보와 등록된 팩터(data/factors.json)를 같은 잣대로 수치 시험합니다.
열쇠가 필요 없습니다(FRED 공개 CSV · 네이버 · 연준 CSV).

python3 scripts/factor_lab.py run [키 ...] [--refresh] [--no-save]
    → data/raw/factor_lab.json (자세한 결과), 도서관 후보마다 'lab' 요약을 고쳐 씀
python3 scripts/factor_lab.py show            → 순위표만 출력

시험 방법 (모든 후보 같은 방식)
  점수: factors.py와 똑같이 — 그날까지 공개된 값(관측일 + lag_days)만, 최근 3년 중 위치를 5등분해 1~5점, direction 반영.
  '매수 쪽 점수' = 유동성(lq)은 점수 그대로, 심리·과열(tc)은 6 − 점수 (높을수록 주식에 좋다는 신호).
  ① 장기(2010-07~, 매주 금요일): 매수 쪽 점수와 1·4·13주 뒤 S&P500 수익률의 순위상관(IC), 나스닥100 4·13주, 앞·뒤 절반, 겹침 감안 유의성(|IC| > 2/√(n/h)).
  ② 최근(2023-09-22~, 풍향계가 있는 기간): 13주 IC, 풍향계와의 상관, 풍향계에 3%를 섞었을 때 13주 IC가 얼마나 바뀌나.
  ③ 신호 성적: 매수 쪽 4~5점 vs 1~2점일 때 13주 뒤 S&P500 평균·오른 비율, 방향 적중(평균 대비),
     급락 맞히기(이후 13주 안에 S&P500이 10% 넘게 빠진 비율 — 매도 쪽 신호일 때 높을수록 좋음).
  ④ 겹침: 지금 쓰는 20개 지표 점수와의 상관 중 가장 큰 것(2023-09~ 매일).
판정(참고용, 결정은 위원회): 유망 / 보통 / 약함 / 반대 / 자료 부족
"""
import datetime as dt
import hashlib
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import factors as FA  # noqa: E402
import sources as SRC  # noqa: E402

ROOT = FA.ROOT
LIB = os.path.join(ROOT, "data", "factor_library.json")
LABDIR = os.path.join(ROOT, "data", "raw", "lab")
OUT = os.path.join(ROOT, "data", "raw", "factor_lab.json")
KST = FA.KST
RECENT = "2023-09-22"
MIX_W = 0.03
REFRESH = "--refresh" in sys.argv


def today():
    return dt.datetime.now(KST).date().isoformat()


def r3(x):
    return None if x is None or (isinstance(x, float) and not np.isfinite(x)) else round(float(x), 3)


# ---------------------------------------------------------------- 원자료 (다리마다 저장, 네이버 선물은 쌓임)
_mem = {}


def get_leg(spec):
    k = json.dumps(spec, sort_keys=True)
    if k in _mem:
        return _mem[k]
    os.makedirs(os.path.join(LABDIR, "legs"), exist_ok=True)
    nm = (spec.get("id") or spec.get("fut") or spec.get("code") or spec.get("col") or "x").replace(".", "_")
    p = os.path.join(LABDIR, "legs", f"{spec['src']}_{nm}_{hashlib.sha1(k.encode()).hexdigest()[:6]}.json")
    old = json.load(open(p, encoding="utf-8")) if os.path.exists(p) else None
    fresh = old and (dt.datetime.now(KST) - dt.datetime.fromisoformat(old["fetched"])).total_seconds() < 18 * 3600
    if fresh and not REFRESH:
        s = SRC._ser(old["value"])
    else:
        s, st = SRC.leg(spec, (old or {}).get("state"))
        json.dump({"spec": spec, "fetched": dt.datetime.now(KST).isoformat(timespec="seconds"), "state": st, "value": SRC._dict(s)},
                  open(p, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    _mem[k] = s
    return s


def raw(key, f, registered=False):
    src = f["source"]
    t = src["type"]
    if registered and t in ("fred", "fred_ratio", "hist"):
        s = FA.raw_series(key, f)                     # 등록된 팩터는 저장소에 받아 둔 자료 그대로
        if len(s):
            return s
    if t == "fred":
        return get_leg({"src": "fred", "id": src["id"]})
    if t == "fred_ratio":
        a, b = get_leg({"src": "fred", "id": src["num"]}), get_leg({"src": "fred", "id": src["den"]})
        j = pd.concat([a, b], axis=1, join="inner").dropna()
        return j.iloc[:, 0] / j.iloc[:, 1]
    if t == "mix":
        a = get_leg(src["num"])
        return SRC.ratio(a, get_leg(src["den"])) if src.get("den") else a
    if t == "calc":
        legs, fn = SRC.CALC_LEGS[src["name"]]
        return fn(*[get_leg(x) for x in legs])
    if t == "hist":
        return FA.raw_series(key, f)
    raise ValueError(t)


# ---------------------------------------------------------------- 잣대
def ic(x, y, h=1):
    m = x.notna() & y.notna()
    n = int(m.sum())
    if n < 40 or x[m].nunique() < 2:
        return None, n, False
    v = float(x[m].corr(y[m], method="spearman"))
    return v, n, bool(abs(v) > 2 / np.sqrt(max(n / h, 1)))


def halves(x, y):
    m = x.notna() & y.notna()
    idx = x[m].index
    if len(idx) < 80:
        return None, None
    k = len(idx) // 2
    a = x[idx[:k]].corr(y[idx[:k]], method="spearman")
    b = x[idx[k:]].corr(y[idx[k:]], method="spearman")
    return r3(a), r3(b)


def context():
    L = FA.long_index()
    js = json.load(open(os.path.join(ROOT, "data", "series.json"), encoding="utf-8"))
    sd = pd.DatetimeIndex(js["dates"])
    cols = js["cols"]
    cur = {}
    for k, v in cols.items():
        if k.startswith("s_tc_") or k.startswith("s_lq_"):
            s = pd.Series(v, index=sd, dtype=float)
            cur[k[2:]] = (6 - s) if k.startswith("s_tc_") else s
    wj = json.load(open(os.path.join(ROOT, "data", "wind.json"), encoding="utf-8"))
    wind = pd.Series(wj["w"], index=pd.DatetimeIndex(wj["dates"]), dtype=float)
    # 장기 비교용: 지금 트렌드캐치의 VIX 점수(고정 구간 <15:5 · 15~20:4 · 20~30:3 · 30~40:2 · >40:1)를 매수 쪽으로 뒤집은 값
    vx, _ = FA.at_dates(get_leg({"src": "fred", "id": "VIXCLS"}), L["spx"].index, 1, 7)
    vs = pd.cut(vx, [-1, 15, 20, 30, 40, 1e9], labels=[5, 4, 3, 2, 1], right=False).astype(float)
    return L, sd, pd.DataFrame(cur), wind, 6 - vs


def evaluate(key, f, ctx, registered=False):
    L, sd, cur, wind, vixbull = ctx
    out = {"key": key, "name": f["name"], "group": f["group"], "direction": f["direction"], "transform": f.get("transform"),
           "chg_days": f.get("chg_days"), "lag_days": f["lag_days"], "source": SRC.describe(f["source"]) if f["source"]["type"] in ("mix", "calc") else
           (f"FRED {f['source'].get('id') or f['source'].get('num') + '/' + f['source'].get('den')}" if f["source"]["type"] != "hist" else "자체 계산")}
    try:
        rs = raw(key, f, registered)
    except Exception as ex:  # noqa: BLE001
        out.update({"판정": "자료 오류", "오류": str(ex)[:160]})
        return out, None
    if rs.empty:
        out.update({"판정": "자료 부족"})
        return out, None
    tr = FA.transformed(f, rs)
    sc = FA.scored(f, tr, int(f.get("window_days") or 1095), int(f.get("min_n") or 20))
    out["자료"] = f"{rs.index[0]:%Y-%m-%d}~{rs.index[-1]:%Y-%m-%d} ({len(rs)}개)"
    vnow, _ = FA.at_dates(tr, [pd.Timestamp(today())], f["lag_days"], f["stale_days"])
    snow, onow = FA.at_dates(sc, [pd.Timestamp(today())], f["lag_days"], f["stale_days"])
    out["지금"] = {"값": r3(vnow.iloc[0]), "점수": None if pd.isna(snow.iloc[0]) else int(snow.iloc[0]),
                  "관측일": None if pd.isna(onow.iloc[0]) else f"{onow.iloc[0]:%Y-%m-%d}"}
    spx = L["spx"]
    D = spx.index
    s, _ = FA.at_dates(sc, D, f["lag_days"], f["stale_days"])
    bull = s if f["group"] == "lq" else 6 - s
    out["표본(주)"] = int(bull.notna().sum())
    res = {}
    for nm, px in L.items():
        px = px.reindex(D)
        for h in ((1, 4, 13) if nm == "spx" else (4, 13)):
            fw = px.shift(-h) / px - 1
            v, n, sig = ic(bull, fw, h)
            res[f"{nm}_{h}주"] = {"ic": r3(v), "n": n, "유의": sig}
            if nm == "spx" and h in (4, 13):
                a, b = halves(bull, fw)
                res[f"{nm}_{h}주"].update({"앞절반": a, "뒤절반": b})
                rec = bull.index >= pd.Timestamp(RECENT)
                v2, n2, _ = ic(bull[rec], fw[rec], h)
                res[f"{nm}_{h}주"]["최근"] = r3(v2)
                res[f"{nm}_{h}주"]["최근n"] = n2
                ex = ~((bull.index >= pd.Timestamp("2019-12-01")) & (bull.index <= pd.Timestamp("2020-12-31")))   # 코로나 한 해에 기대는지
                v3, _, _ = ic(bull[ex], fw[ex], h)
                res[f"{nm}_{h}주"]["2020빼고"] = r3(v3)
    out["IC"] = res
    fw13 = spx.shift(-13) / spx - 1
    # 급락 맞히기: 이후 13주 안에 S&P500이 지금보다 10% 넘게 빠진 적이 있었나(주간 종가 기준)
    fmin = pd.concat([spx.shift(-i) for i in range(1, 14)], axis=1).min(axis=1)
    crash = (fmin / spx - 1 <= -0.10).astype(float).where(spx.shift(-13).notna())
    mc = bull.notna() & crash.notna()
    if mc.sum() >= 40:
        cb, cy = bull[mc], crash[mc]
        out["급락_13주안_10%"] = {"전체%": r3(cy.mean() * 100),
                              "매도쪽(1~2점)일때%": r3(cy[cb <= 2].mean() * 100) if (cb <= 2).any() else None,
                              "매수쪽(4~5점)일때%": r3(cy[cb >= 4].mean() * 100) if (cb >= 4).any() else None,
                              "n_매도쪽": int((cb <= 2).sum()), "n_매수쪽": int((cb >= 4).sum())}
    m = bull.notna() & fw13.notna()
    if m.sum() >= 40:
        b, y = bull[m], fw13[m]
        hi, lo = y[b >= 4], y[b <= 2]
        nz = b != 3
        hit = ((np.sign(y[nz] - y.mean()) == np.sign(b[nz] - 3)).mean()) if nz.any() else np.nan
        out["신호성적_13주"] = {"매수쪽(4~5점)": {"n": int(len(hi)), "평균%": r3(hi.mean() * 100) if len(hi) else None, "오른비율%": r3((hi > 0).mean() * 100) if len(hi) else None},
                            "매도쪽(1~2점)": {"n": int(len(lo)), "평균%": r3(lo.mean() * 100) if len(lo) else None, "오른비율%": r3((lo > 0).mean() * 100) if len(lo) else None},
                            "전체평균%": r3(y.mean() * 100), "방향적중%(평균대비)": r3(hit * 100)}
        # 장기: 지금 쓰는 VIX 점수와 얼마나 같은지, VIX 몫을 뺀 나머지도 맞히는지
        mv = m & vixbull.notna()
        if mv.sum() >= 40 and bull[mv].nunique() > 1:
            x, z = bull[mv].astype(float), vixbull[mv].astype(float)
            beta = np.polyfit(z, x, 1)
            resid = x - np.polyval(beta, z)
            out["장기_VIX점수와"] = {"상관": r3(x.corr(z, method="spearman")), "VIX몫_뺀_13주IC": r3(resid.corr(fw13[mv], method="spearman"))}
    # 겹침(2023-09~ 매일) · 풍향계 추가 효과(2023-09~ 매주)
    sdaily, _ = FA.at_dates(sc, sd, f["lag_days"], f["stale_days"])
    bd = (sdaily if f["group"] == "lq" else 6 - sdaily)
    rec = sd >= pd.Timestamp(RECENT)
    cc = {}
    for c in cur.columns:
        mm = rec & bd.notna().values & cur[c].notna().values
        if mm.sum() > 60 and bd[mm].nunique() > 1 and cur[c][mm].nunique() > 1:
            cc[c] = float(bd[mm].corr(cur[c][mm], method="spearman"))
    if cc:
        k = max(cc, key=lambda z: abs(cc[z]))
        out["겹침_최대"] = {"지표": k, "상관": r3(cc[k])}
    W = wind.reindex(D)
    rr = D >= pd.Timestamp(RECENT)
    mm = rr & W.notna().values & bull.notna().values
    if mm.sum() > 40:
        out["풍향계와_상관"] = r3(pd.Series(W[mm]).corr(bull[mm], method="spearman"))
        eff = {}
        for h in (4, 13):
            fw = spx.shift(-h) / spx - 1
            base, n, _ = ic(W[mm], fw[mm], h)
            mixd = (1 - MIX_W) * W[mm] + MIX_W * (bull[mm] - 1) / 4 * 100
            new, _, _ = ic(mixd, fw[mm], h)
            eff[f"{h}주"] = {"지금": r3(base), "섞으면": r3(new), "변화": r3(new - base) if base is not None and new is not None else None, "n": n}
        out["풍향계에_3%_섞기"] = eff
    out["판정"] = verdict(out)
    return out, bull


def verdict(o):
    I = o.get("IC") or {}
    a13, a4 = (I.get("spx_13주") or {}), (I.get("spx_4주") or {})
    v13 = a13.get("ic")
    if v13 is None:
        return "자료 부족"
    same = all(x is not None and x > 0 for x in (a13.get("앞절반"), a13.get("뒤절반"), a13.get("2020빼고")))
    rec = a13.get("최근")
    if v13 >= 0.10 and same and (rec is None or rec >= 0) and (a13.get("유의") or a4.get("유의")):
        return "유망"
    if v13 >= 0.05 and same:
        return "보통"
    if v13 <= -0.10 and all(x is not None and x < 0 for x in (a13.get("앞절반"), a13.get("뒤절반"))):
        return "반대"
    return "약함"


def run(only=None, save=True):
    lib = json.load(open(LIB, encoding="utf-8"))
    R = FA.load()
    ctx = context()
    todo = [(k, c["def"], False, "도서관") for k, c in lib["candidates"].items() if c.get("def") and k not in R["factors"]]
    todo += [(k, f, True, "등록:" + f.get("status", "")) for k, f in R["factors"].items() if f.get("status") in ("watch", "active")]
    if only:
        todo = [t for t in todo if t[0] in only]
    results, bulls = {}, {}
    for k, f, reg, where in todo:
        o, b = evaluate(k, f, ctx, reg)
        o["어디"] = where
        results[k] = o
        if b is not None:
            bulls[k] = b
        print(f"{k:10s} {o.get('판정'):6s} 13주IC={((o.get('IC') or {}).get('spx_13주') or {}).get('ic')}", file=sys.stderr)
    # 후보끼리 겹침(장기 매주)
    B = pd.DataFrame(bulls)
    if not B.empty:
        C = B.corr(method="spearman")
        for k in B.columns:
            oth = C[k].drop(k).dropna()
            if len(oth):
                j = oth.abs().idxmax()
                results[k]["후보끼리_겹침_최대"] = {"키": j, "상관": r3(oth[j])}
    L, _, _, _, vb = ctx
    base = {}
    for h in (4, 13):
        fw = L["spx"].shift(-h) / L["spx"] - 1
        v, n, sig = ic(vb, fw, h)
        base[f"{h}주"] = {"ic": r3(v), "n": n, "유의": sig}
    rank = sorted([k for k in results if (results[k].get("IC") or {}).get("spx_13주", {}).get("ic") is not None],
                  key=lambda k: -results[k]["IC"]["spx_13주"]["ic"])
    out = {"date": today(), "방법": __doc__.split("시험 방법")[1].strip() if "시험 방법" in __doc__ else "",
           "주의": "후보를 여럿 시험하면 우연히 좋아 보이는 것이 생깁니다. 장기·앞뒤 절반·최근이 모두 같은 방향인지 함께 보세요. 판정은 참고용이고 결정은 위원회가 합니다.",
           "기준선_지금_VIX점수(장기)": base,
           "순위_13주IC": [{"키": k, "이름": results[k]["name"], "13주IC": results[k]["IC"]["spx_13주"]["ic"], "판정": results[k]["판정"], "어디": results[k]["어디"]} for k in rank],
           "results": results}
    if save:
        os.makedirs(os.path.dirname(OUT), exist_ok=True)
        json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        for k, c in lib["candidates"].items():
            if k in results:
                c["lab"] = summary(results[k])
        lib["lab_date"] = today()
        json.dump(lib, open(LIB, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return out


def summary(o):
    I = o.get("IC") or {}
    g = lambda k, f="ic": (I.get(k) or {}).get(f)  # noqa: E731
    return {"date": today(), "판정": o.get("판정"), "장기_4주IC": g("spx_4주"), "장기_13주IC": g("spx_13주"), "나스닥100_13주IC": g("ndx_13주"),
            "앞절반_13주": g("spx_13주", "앞절반"), "뒤절반_13주": g("spx_13주", "뒤절반"), "최근_13주IC": g("spx_13주", "최근"), "2020빼고_13주IC": g("spx_13주", "2020빼고"),
            "겹침_최대": o.get("겹침_최대"), "장기_VIX점수와": o.get("장기_VIX점수와"), "풍향계_섞기_13주변화": ((o.get("풍향계에_3%_섞기") or {}).get("13주") or {}).get("변화"),
            "급락_13주안_10%": o.get("급락_13주안_10%"), "지금": o.get("지금"), **({"오류": o["오류"]} if o.get("오류") else {})}


def sync_status():
    """도서관 후보의 상태를 등록부(data/factors.json)에 맞춘다: watch → 관찰, active → 사용, removed → 뺌."""
    lib = json.load(open(LIB, encoding="utf-8"))
    R = FA.load()
    word = {"watch": "관찰", "active": "사용", "removed": "뺌"}
    for k, c in lib["candidates"].items():
        f = R["factors"].get(k)
        if f and f.get("status") in word:
            c["status"] = word[f["status"]]
            c["registered"] = f.get("added")
    json.dump(lib, open(LIB, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def show():
    o = json.load(open(OUT, encoding="utf-8"))
    print(o["date"])
    for x in o["순위_13주IC"]:
        r = o["results"][x["키"]]
        I = r["IC"]
        print(f"{x['키']:9s} {x['판정']:4s} 13주 {I['spx_13주']['ic']:+.3f} (앞 {I['spx_13주'].get('앞절반')} 뒤 {I['spx_13주'].get('뒤절반')} 최근 {I['spx_13주'].get('최근')} 2020빼고 {I['spx_13주'].get('2020빼고')})"
              f" 4주 {I['spx_4주']['ic']:+.3f} 1주 {I['spx_1주']['ic']} NDX13 {I['ndx_13주']['ic']}  겹침 {r.get('겹침_최대')} VIX {r.get('장기_VIX점수와')}  섞기 {((r.get('풍향계에_3%_섞기') or {}).get('13주') or {}).get('변화')}  [{x['어디']}] {x['이름']}")


if __name__ == "__main__":
    a = [x for x in sys.argv[1:] if not x.startswith("--")]
    if not a or a[0] not in ("run", "show"):
        sys.exit(__doc__)
    if a[0] == "run":
        run(a[1:] or None, save="--no-save" not in sys.argv)
        show()
    else:
        show()
