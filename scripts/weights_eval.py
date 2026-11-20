"""가중치 점검 도구 — 매주 토요일 (주간 · 월간 · 분기).
가장 최신 Claude 모델(지금 Claude Fable 5.2)이 근거를 보고 결정하고, Opus가 근거 자료를 만들고 결정을 그대로 적용한다.

python3 scripts/weights_eval.py due [YYYY-MM-DD]       → 그날(기본: 오늘 한국 시각)의 점검 단계: weekly | monthly | quarterly | no | done(이미 함·진행 중)
python3 scripts/weights_eval.py brief [단계]            → data/raw/weights_brief.json  (근거 자료: 풍향계 방향 적중 점검 + 지표별·종합 점수와 이후 지수의 관계)
python3 scripts/weights_eval.py test  후보.json         → 후보 가중치였다면 종합 점수·풍향계가 이후 지수를 얼마나 맞혔을지 + 단계별 한도 검사
python3 scripts/weights_eval.py apply 결정.json         → 한도 검사 통과 시 data/weights.json 에 새 버전(다음 거래일부터) 또는 '유지' 기록

단계(rules.levels): 매달 첫 토요일 = 월간(1·4·7·10월 첫 토요일은 분기), 나머지 토요일 = 주간.
한 번에 움직일 수 있는 폭은 분기 > 월간 > 주간.

후보.json / 결정.json 형식:
{"level": "weekly" | "monthly" | "quarterly", "decision": "변경" | "유지", "by": "Claude Fable 5.2",
 "summary": "초보자용 3~5문장", "direction_note": "풍향계 방향이 맞았는지 1~2문장(근거 숫자)",
 "tc": {"fg": 11.1, ...9개, 합 100}, "lq": {"fed": 14, ...11개, 합 100}, "wind": {"sent": 0.6},
 "reasons": {"tc.vix" | "lq.hy" | "wind": "바꾼 이유(숫자 근거)"}}

'맞힌 정도' = 순위상관(Spearman, −1~+1). 매주 마지막 거래일의 점수와 그날부터 5·20·60거래일(약 1주·1개월·3개월) 뒤 지수 수익률.
트렌드캐치는 역발상이라 '−'가 맞는 방향(점수 높을수록 그 뒤 수익 낮음), 유동성·풍향계는 '+'가 맞는 방향.
"""
import datetime as dt
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import weights as WM  # noqa: E402
import factors as FA  # noqa: E402

ROOT = WM.ROOT
DATA = os.path.join(ROOT, "data")
RAW = os.path.join(DATA, "raw")
HS = (20, 60)
IDX = {"spx": "S&P500", "ndx": "나스닥100", "kospi": "코스피"}
LEVEL_KO = {"weekly": "주간", "monthly": "월간", "quarterly": "분기"}
TC_NAME = {"fg": "공포탐욕", "aaii": "AAII 강세−약세", "vix": "VIX", "hy": "하이일드 스프레드", "pc": "풋콜 비율",
           "margin": "신용융자 YoY", "a200": "S&P500 200일선 위 비율", "rsi": "RSI(14일)", "dev": "200일선 이격도"}
LQ_NAME = {"fed": "연준 총자산 3개월 변화", "nl": "순유동성 3개월 변화", "m2": "M2 YoY", "effr": "기준금리 3개월 변화",
           "hy": "하이일드 스프레드", "dxy": "달러 6개월 변화", "margin": "신용융자 YoY", "bank": "상업은행 신용 YoY",
           "vol": "거래량(20일 평균 대비)", "nfci": "NFCI 금융여건", "y10": "10년물 금리"}
KST = dt.timezone(dt.timedelta(hours=9))


def r(x, n=3):
    return None if x is None or (isinstance(x, float) and np.isnan(x)) else round(float(x), n)


def today_kst():
    return dt.datetime.now(KST).date()


def load_df(extra=None):
    """series.json + 사용 중(active)인 새 팩터 점수(없으면 등록부 원자료로 계산). extra: 더 붙일 팩터 키."""
    s = json.load(open(os.path.join(DATA, "series.json"), encoding="utf-8"))
    df = pd.DataFrame(s["cols"], index=pd.to_datetime(s["dates"]))
    R = FA.load()
    want = [k for k in FA.keys(R) + list(extra or []) if f"s_{R['factors'][k]['group']}_{k}" not in df]
    if want:
        df = pd.concat([df, FA.frame(df.index, want, R)], axis=1)
    return df


def name_of(grp, k):
    base = TC_NAME if grp == "tc" else LQ_NAME
    if k in base:
        return base[k]
    f = FA.load()["factors"].get(k)
    return f["name"] if f else k


def committee_result(level=None):
    """오늘 위원회 합의 결과(data/raw/committee_result.json). 없거나 날짜·단계가 다르면 빈 결과."""
    p = os.path.join(RAW, "committee_result.json")
    empty = {"adds": [], "removes": [], "registers": []}
    if not os.path.exists(p):
        return empty
    c = json.load(open(p, encoding="utf-8"))
    if c.get("date") != today_kst().isoformat() or (level and c.get("level") != level):
        return empty
    return c


def weekly_idx(df):
    """마지막 날부터 5거래일 간격(주 1회) 표본."""
    n = len(df)
    return sorted(range(n - 1, -1, -5))


def ic(score, ret, nmin=20):
    m = score.notna() & ret.notna()
    n = int(m.sum())
    if n < nmin or score[m].nunique() < 2 or ret[m].nunique() < 2:
        return None, n
    return r(score[m].corr(ret[m], method="spearman")), n


def fwd(df, ix, h):
    px = df[ix].astype(float)
    return px.shift(-h) / px - 1


def sig(v, n, h):
    """겹치는 기간을 감안한 대략적 유의 기준: |IC| > 2 / √(n ÷ (h/5))"""
    if v is None or n < 10:
        return None
    return bool(abs(v) > 2 / np.sqrt(max(n / max(h / 5, 1), 1)))


def zone(w):
    if w is None or np.isnan(w):
        return None
    return "강한 역풍" if w < 30 else "역풍" if w < 45 else "무풍" if w < 55 else "순풍" if w < 70 else "강한 순풍"


# ---------------------------------------------------------------- 단계 · 일정
def level_of(d):
    """토요일만 점검. 매달 첫 토요일 = 월간(1·4·7·10월은 분기), 나머지 토요일 = 주간."""
    if d.weekday() != 5:
        return None
    if d.day <= 7:
        return "quarterly" if d.month in (1, 4, 7, 10) else "monthly"
    return "weekly"


def set_next(W, today):
    t = dt.date.fromisoformat(today) if isinstance(today, str) else today
    d = t + dt.timedelta(days=1)
    while d.weekday() != 5:
        d += dt.timedelta(days=1)
    sc = W.setdefault("rules", {}).setdefault("schedule", {})
    sc["next"], sc["next_level"] = d.isoformat(), level_of(d)


# ---------------------------------------------------------------- 성적 계산
def score_stats(df, sc, sign):
    """점수 하나(sc, 날짜 index)의 이후 수익률 관계. sign: 맞는 방향(−1 트렌드캐치, +1 유동성·풍향계)."""
    wk = weekly_idx(df)
    out = {}
    for ix in IDX:
        for h in HS:
            f = fwd(df, ix, h)
            a, b = sc.iloc[wk], f.iloc[wk]
            v, n = ic(a, b)
            m = a.notna() & b.notna()
            idx = a[m].index
            half = len(idx) // 2
            v1, _ = ic(a[idx[:half]], b[idx[:half]]) if half >= 20 else (None, 0)
            v2, _ = ic(a[idx[half:]], b[idx[half:]]) if half >= 20 else (None, 0)
            v52, _ = ic(a[idx[-52:]], b[idx[-52:]], nmin=30)
            v26, _ = ic(a[idx[-26:]], b[idx[-26:]], nmin=15)
            out[f"{ix}_{h}"] = {"ic": v, "n주": n, "맞는방향_강도": r(v * sign) if v is not None else None, "유의": sig(v, n, h),
                                "앞절반": v1, "뒤절반": v2, "최근52주": v52, "최근26주": v26}
    return out


def same_week(df, sc):
    """같은 주 움직임과의 관계: 점수의 1주 변화 vs 같은 주 S&P500 수익률(최근 52주). 크면 '주가를 따라가는' 신호."""
    wk = weekly_idx(df)
    a = sc.iloc[wk].diff()
    b = df["spx"].astype(float).iloc[wk].pct_change()
    v, n = ic(a.iloc[-52:], b.iloc[-52:], nmin=20)
    return v


def wind_series(df, ver=None, W=None):
    c = WM.composite(df, ver=ver, W=W)
    w, _, _, _ = WM.wind_parts(c["tc"], c["lq"], ver=ver, W=W)
    return c, w


def composite_eval(df, ver):
    c, w = wind_series(df, ver=ver)
    res = {"트렌드캐치": score_stats(df, c["tc"], -1), "유동성": score_stats(df, c["lq"], +1), "풍향계": score_stats(df, w, +1)}
    f60 = fwd(df, "spx", 60) * 100
    z = pd.cut(w, [-1, 30, 45, 55, 70, 101], labels=["강한 역풍", "역풍", "무풍", "순풍", "강한 순풍"], right=False)
    zs = {}
    for nm in ["강한 역풍", "역풍", "무풍", "순풍", "강한 순풍"]:
        m = (z == nm) & f60.notna()
        zs[nm] = {"평균%": r(f60[m].mean(), 2) if m.any() else None, "오른비율%": r((f60[m] > 0).mean() * 100, 0) if m.any() else None, "일수": int(m.sum())}
    res["풍향계_구간별_60거래일뒤_S&P500"] = zs
    res["풍향계_마지막값"] = r(w.dropna().iloc[-1], 1) if w.notna().any() else None
    return res


def headline(ev):
    """한눈에 비교할 핵심 숫자(맞는 방향 강도, 클수록 좋음). 풍향계는 최근 기간도 함께."""
    out = {}
    for k, sign in (("트렌드캐치", -1), ("유동성", 1), ("풍향계", 1)):
        d = {kk: (ev[k].get(kk) or {}).get("맞는방향_강도") for kk in ("spx_20", "spx_60", "ndx_60", "kospi_20")}
        for kk, win in (("spx_20", "최근26주"), ("spx_60", "최근52주")):
            v = (ev[k].get(kk) or {}).get(win)
            d[f"{kk}_{win}"] = r(v * sign) if v is not None else None
        out[k] = d
    return out


def direction_check(df, w):
    """풍향계가 가리킨 방향이 맞았는지: 순풍(55↑)이면 그 뒤 올랐나, 역풍(45↓)이면 그 뒤 약했나. 매주 1회 표본, S&P500 기준."""
    wk = weekly_idx(df)
    out = {}
    for h, hn in ((5, "1주 뒤"), (20, "1개월 뒤"), (60, "3개월 뒤")):
        f = fwd(df, "spx", h) * 100
        a, b = w.iloc[wk], f.iloc[wk]
        m = a.notna() & b.notna()
        a, b = a[m], b[m]
        res = {}
        for nm, n in (("최근13주", 13), ("최근26주", 26), ("최근52주", 52), ("전체", None)):
            aa, bb = (a.iloc[-n:], b.iloc[-n:]) if n else (a, b)
            if len(aa) < 4:
                res[nm] = {"표본(주)": len(aa), "메모": "결과가 나온 신호가 아직 적음"}
                continue
            avg = bb.mean()
            up, dn = aa >= 55, aa < 45
            mid = ~up & ~dn
            grp = lambda mm: {"횟수": int(mm.sum()), "평균%": r(bb[mm].mean(), 2) if mm.any() else None,
                              "오른비율%": r((bb[mm] > 0).mean() * 100, 0) if mm.any() else None}
            nd = int(up.sum() + dn.sum())
            res[nm] = {"표본(주)": len(aa), "같은기간_평균%": r(avg, 2), "같은기간_오른비율%": r((bb > 0).mean() * 100, 0),
                       "순풍(55↑)": grp(up), "무풍(45~55)": grp(mid), "역풍(45↓)": grp(dn),
                       "방향적중_부호": f"{int((up & (bb > 0)).sum() + (dn & (bb < 0)).sum())}/{nd}",
                       "방향적중_평균대비": f"{int((up & (bb > avg)).sum() + (dn & (bb < avg)).sum())}/{nd}",
                       "순위상관": ic(aa, bb, nmin=8)[0]}
        out[hn] = res
    # 최근 8주 신호 성적표
    rows = []
    for i in wk[-8:]:
        wv = w.iloc[i]
        row = {"날짜": f"{df.index[i]:%Y-%m-%d}", "풍향계": r(wv, 1), "구간": zone(wv)}
        for h, hn in ((5, "1주"), (20, "1개월")):
            for ix in IDX:
                v = fwd(df, ix, h).iloc[i]
                row[f"{IDX[ix]}_{hn}뒤%"] = r(v * 100, 2) if not np.isnan(v) else "아직 모름"
            v = fwd(df, "spx", h).iloc[i]
            z = zone(wv)
            if np.isnan(v):
                row[f"판정_{hn}"] = "아직 모름"
            elif z in ("무풍", None):
                row[f"판정_{hn}"] = "관망 구간(판정 안 함)"
            else:
                good = z.endswith("순풍")
                row[f"판정_{hn}"] = "맞음" if (good and v > 0) or (not good and v < 0) else "틀림"
        rows.append(row)
    out["최근8주_신호_성적표"] = rows
    out["_읽는법"] = ("방향적중_부호 = 순풍인데 그 뒤 올랐거나 역풍인데 그 뒤 내린 횟수 / 순풍·역풍 신호 수. "
                    "방향적중_평균대비 = 순풍이면 같은 기간 평균보다 높았고 역풍이면 낮았던 횟수(상승장에서는 이쪽이 더 공정). "
                    "최근 기간일수록 표본이 적어 우연이 크게 섞입니다.")
    return out


def check_summary(dc):
    """점검 기록에 남길 짧은 방향 점검 요약(숫자만)."""
    out = {}
    for hn, win in (("1개월 뒤", "최근26주"), ("3개월 뒤", "최근52주")):
        d = (dc.get(hn) or {}).get(win) or {}
        if "순풍(55↑)" not in d:
            continue
        u, dn = d["순풍(55↑)"], d["역풍(45↓)"]
        fmt = lambda g: f"{g['횟수']}회, 그 뒤 평균 {g['평균%']}%" if g["횟수"] else "0회"
        out[f"{win}·{hn}"] = {"순풍": fmt(u), "역풍": fmt(dn),
                             "같은기간_평균%": d["같은기간_평균%"], "방향적중_평균대비": d["방향적중_평균대비"], "순위상관": d["순위상관"]}
    return out


# ---------------------------------------------------------------- 한도 검사
def check(cand, cur, rules, level, com=None):
    """단계별 한도 검사. com: 위원회 합의 결과(넣을 팩터는 정해진 가중치로, 뺄 팩터는 빼고). 반환: (통과 여부, 오류 목록, 새 가중치(%))"""
    errs = []
    new = {}
    L = (rules.get("levels") or {}).get(level)
    if not L:
        return False, [f"level '{level}' 없음 — weekly | monthly | quarterly"], {}
    com = com or {"adds": [], "removes": []}
    step = {"tc": L["tc_step"], "lq": L["lq_step"]}
    REG = FA.load()["factors"]
    for grp in ("tc", "lq"):
        adds = {a["key"]: float(a["weight"]) for a in com.get("adds", []) if a["group"] == grp}
        rems = {x["key"] for x in com.get("removes", []) if x["group"] == grp}
        want = [k for k in WM.keys_of(cur, grp) if k not in rems] + [k for k in adds if k not in cur[grp]]
        d = cand.get(grp) or {}
        miss, extra = [k for k in want if k not in d], [k for k in d if k not in want]
        if miss:
            errs.append(f"{grp}: 빠진 지표 {miss}")
        if extra:
            errs.append(f"{grp}: 넣을 수 없는 지표 {extra} (새 팩터는 위원회 합의로만 넣고, 뺄 지표는 위원회 결과대로 뺍니다)")
        if miss or extra:
            continue
        if any(float(d[k]) <= 0 for k in want):
            errs.append(f"{grp}: 0 이하 가중치는 안 됨(지표 빼기는 위원회 합의로만)")
            continue
        tot = sum(float(d[k]) for k in want)
        if abs(tot - 100) > 0.05:
            errs.append(f"{grp}: 가중치 합이 {tot:.2f} — 100이 되게 맞춰 주세요(올린 만큼 다른 곳에서 내리기)")
        nn = WM.norm(d, want)
        cc = WM.norm(cur[grp])
        R = rules[grp]
        for k in want:
            lo = R["min"] if k in (WM.TC_KEYS if grp == "tc" else WM.LQ_KEYS) else rules.get("new_min", 0.5)
            if k in adds:
                if abs(nn[k] - adds[k]) > 0.011:
                    errs.append(f"{grp}.{k}: 새로 넣는 팩터는 위원회가 정한 {adds[k]}%로 시작합니다(지금 {nn[k]:.2f}%)")
                continue
            if not lo - 1e-6 <= nn[k] <= R["max"] + 1e-6:
                errs.append(f"{grp}.{k}: {nn[k]:.2f}% — 허용 범위 {lo}~{R['max']}% 밖")
            if abs(nn[k] - cc[k]) > step[grp] + 1e-6:
                errs.append(f"{grp}.{k}: {cc[k]:.2f}% → {nn[k]:.2f}% — {LEVEL_KO[level]} 점검은 한 번에 ±{step[grp]}%p까지")
            if abs(nn[k] - cc[k]) >= 0.05 and not (cand.get("reasons") or {}).get(f"{grp}.{k}"):
                errs.append(f"{grp}.{k}: 바꿨으면 reasons[\"{grp}.{k}\"]에 이유가 있어야 함")
        allk = set(want) | set(cc)
        to = sum(max(nn.get(k, 0) - cc.get(k, 0), 0) for k in allk)
        if to > L["max_turnover"] + 1e-6:
            errs.append(f"{grp}: 옮긴 가중치 합 {to:.2f}%p(넣기·빼기 포함) — {LEVEL_KO[level]} 점검은 한 번에 {L['max_turnover']}%p까지")
        mn = (rules.get("min_count") or {}).get(grp, 0)
        if len(want) < mn:
            errs.append(f"{grp}: 지표가 {len(want)}개 — 최소 {mn}개는 있어야 합니다")
        new[grp] = {k: round(nn[k], 2) for k in want}
    ws = (cand.get("wind") or {}).get("sent")
    R = rules["wind_sent"]
    if ws is None:
        errs.append("wind.sent 없음")
    else:
        ws = float(ws)
        if not R["min"] - 1e-9 <= ws <= R["max"] + 1e-9:
            errs.append(f"wind.sent {ws} — 허용 범위 {R['min']}~{R['max']} 밖")
        if abs(ws - cur["wind"]["sent"]) > L["sent_step"] + 1e-9:
            errs.append(f"wind.sent {cur['wind']['sent']} → {ws} — {LEVEL_KO[level]} 점검은 한 번에 ±{L['sent_step']}까지")
        if abs(ws - cur["wind"]["sent"]) > 1e-9 and not (cand.get("reasons") or {}).get("wind"):
            errs.append("wind: 바꿨으면 reasons.wind에 이유가 있어야 함")
        new["wind"] = {"sent": round(ws, 4), "liq": round(1 - ws, 4)}
    if not (cand.get("summary") or "").strip():
        errs.append("summary(초보자용 설명) 없음")
    return not errs, errs, new


def next_trading_day(d):
    d = d + dt.timedelta(days=1)
    while d.weekday() >= 5:
        d += dt.timedelta(days=1)
    return d


# ---------------------------------------------------------------- 명령
def cmd_brief(level):
    df = load_df()
    W = WM.load()
    cur = WM.current(W)
    if level not in W["rules"]["levels"]:
        sys.exit(f"단계 '{level}' 없음 — weekly | monthly | quarterly")
    ana = json.load(open(os.path.join(DATA, "analysis.json"), encoding="utf-8"))
    wk = weekly_idx(df)
    ind = {}
    REG = FA.load()["factors"]
    for grp, sign in (("tc", -1), ("lq", +1)):
        keys = WM.keys_of(cur, grp)
        cw = WM.norm(cur[grp], keys)
        for k in keys:
            sc = df[f"s_{grp}_{k}"].astype(float)
            a = sc.iloc[wk]
            long = ((ana.get("items") or {}).get(f"{grp}_{k}") or {}).get("spx") or {}
            if k in REG:  # 새로 넣은 팩터: 장기 성적은 factors.long_stats
                ls = FA.long_stats(k, REG[k])
                long = {}
            ind[f"{grp}.{k}"] = {
                "이름": name_of(grp, k), "그룹": "트렌드캐치" if grp == "tc" else "유동성", "맞는방향": "−(역발상)" if sign < 0 else "+",
                "새_팩터": k in REG,
                "지금_가중치%": round(cw[k], 2), "지금_점수": r(sc.dropna().iloc[-1], 1) if sc.notna().any() else None,
                "4주전_점수": r(sc.iloc[wk[-5]], 1) if len(wk) > 5 and not np.isnan(sc.iloc[wk[-5]]) else None,
                "점수있는_주%": r(a.notna().mean() * 100, 0), "점수_바뀐_횟수(주)": int((a.dropna().diff() != 0).sum()),
                "점수_종류": sorted(set(int(x) for x in a.dropna().unique())),
                "같은주_주가와_동행(최근52주)": same_week(df, sc),
                "2023이후": score_stats(df, sc, sign),
                "장기(2010~, analysis.json)": {"시작": long.get("start"), "ic_4주": (long.get("ic") or {}).get("4"),
                                              "ic_13주": (long.get("ic") or {}).get("13"), "유의_13주": (long.get("sig") or {}).get("13"),
                                              "지난13주_반영": long.get("past13"), "역할": long.get("role"),
                                              "방향": long.get("direction"), "앞뒤절반_같은방향": long.get("stable"), "절반별": long.get("half")} if long else
                    (ls if k in REG else "장기 자료 없음(과거 자료를 받을 수 없는 지표)"),
            }
    ev = composite_eval(df, cur)
    _, w = wind_series(df, W=W)  # 실제로 발행된 풍향계(그 시점 가중치 버전)
    dc = direction_check(df, w)
    L = W["rules"]["levels"][level]
    out = {
        "_안내": "가중치를 판단할 근거 자료. 숫자 뜻은 WEIGHTS.md 2절. '맞는방향_강도'가 클수록 그 점수가 이후 지수를 잘 맞혔다는 뜻(트렌드캐치는 부호를 뒤집어 계산).",
        "이번_점검": {"단계": level, "이름": LEVEL_KO[level], "한도": L, "중점": L.get("중점")},
        "자료기간": f"{df.index[0]:%Y-%m-%d} ~ {df.index[-1]:%Y-%m-%d} (매주 1회 표본, 5·20·60거래일 뒤 수익률)",
        "풍향계_방향_점검": dc,
        "지금_가중치": {"버전": cur["v"], "적용_시작": cur["from"], "정한_날": cur["set"], "정한_이": cur["by"],
                     "트렌드캐치%": {k: round(v, 2) for k, v in WM.norm(cur["tc"], WM.keys_of(cur, "tc")).items()},
                     "유동성%": {k: round(v, 2) for k, v in WM.norm(cur["lq"], WM.keys_of(cur, "lq")).items()},
                     "풍향계_심리비중": cur["wind"]["sent"], "풍향계_식": WM.formula(cur)[0]},
        "범위": {k: W["rules"][k] for k in ("tc", "lq", "wind_sent")},
        "지금_가중치_성적": ev, "지금_가중치_핵심": headline(ev),
        "지표별": ind,
        "지난_점검": W.get("reviews", [])[-8:],
        "위원회_결과(오늘)": committee_result(level),
        "위원회_안내": "새 팩터 넣기·빼기는 위원회(Fable 2 · Opus 3)가 합의한 것만 반영합니다. 위원회_결과의 adds는 정해진 가중치 그대로 넣고, removes는 빼고, 나머지 지표로 합 100을 맞추세요. 결과가 비어 있으면 지표 목록은 그대로입니다.",
        "적용_시작일(새 버전일 때)": f"{next_trading_day(df.index[-1].date()):%Y-%m-%d}",
    }
    os.makedirs(RAW, exist_ok=True)
    p = os.path.join(RAW, "weights_brief.json")
    json.dump(out, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps({"brief": os.path.relpath(p, ROOT), "단계": LEVEL_KO[level], "기간": out["자료기간"],
                      "방향점검": check_summary(dc), "지금_핵심": out["지금_가중치_핵심"]["풍향계"]}, ensure_ascii=False))


def cmd_test(path):
    df = load_df()
    W = WM.load()
    cur = WM.current(W)
    cand = json.load(open(path, encoding="utf-8"))
    level = cand.get("level")
    com = committee_result(level)
    ok, errs, new = check(cand, cur, W["rules"], level, com)
    log = os.path.join(RAW, "weights_tests.log")
    os.makedirs(RAW, exist_ok=True)
    n_before = sum(1 for _ in open(log, encoding="utf-8")) if os.path.exists(log) else 0
    with open(log, "a", encoding="utf-8") as f:
        f.write(json.dumps({"at": dt.datetime.now().isoformat(timespec="seconds"), "file": path, "ok": ok}, ensure_ascii=False) + "\n")
    lim = ((W["rules"].get("levels") or {}).get(level) or {}).get("후보_시험")
    out = {"한도검사_통과": ok, "오류": errs, "이번_점검_시험_횟수": n_before + 1, "시험_한도": lim}
    if lim and n_before + 1 > lim:
        out["경고"] = f"시험 한도({lim}회)를 넘었습니다. 과적합 위험 — 지금까지의 후보 중에서 고르거나 '유지'하세요."
    if "tc" in new and "lq" in new and "wind" in new:
        ver = {"tc": new["tc"], "lq": new["lq"], "wind": new["wind"]}
        a, b = composite_eval(df, cur), composite_eval(df, ver)
        ha, hb = headline(a), headline(b)
        out["핵심_비교(맞는방향_강도, 클수록 좋음)"] = {k: {kk: {"지금": ha[k][kk], "후보": hb[k][kk]} for kk in ha[k]} for k in ha}
        out["후보_풍향계_구간별_60거래일뒤_S&P500"] = b["풍향계_구간별_60거래일뒤_S&P500"]
        out["지금_풍향계_구간별_60거래일뒤_S&P500"] = a["풍향계_구간별_60거래일뒤_S&P500"]
        out["후보_풍향계_기간별(spx_60)"] = {kk: b["풍향계"]["spx_60"][kk] for kk in ("앞절반", "뒤절반", "최근52주")}
        out["지금_풍향계_기간별(spx_60)"] = {kk: a["풍향계"]["spx_60"][kk] for kk in ("앞절반", "뒤절반", "최근52주")}
        out["후보_풍향계_마지막값"], out["지금_풍향계_마지막값"] = b["풍향계_마지막값"], a["풍향계_마지막값"]
        out["주의"] = "같은 자료로 여러 번 맞춰 보면 과거에만 잘 맞는 가중치가 됩니다(과적합). 최근 기간만이 아니라 앞절반·뒤절반·장기(2010~) 근거와도 같은 방향인지 보세요."
    print(json.dumps(out, ensure_ascii=False, indent=1))
    sys.exit(0 if ok else 1)


def apply_committee(com, start, today, by_version):
    """위원회 합의를 등록부(data/factors.json)에 반영: 넣은 팩터 active, 뺀 새 팩터 removed, 새 후보 watch 등록."""
    R = FA.load()
    for a in com.get("adds", []):
        f = R["factors"][a["key"]]
        f.update({"status": "active", "activated": start, "init_weight": a["weight"]})
    for x in com.get("removes", []):
        if x["key"] in R["factors"]:
            R["factors"][x["key"]].update({"status": "removed", "removed": start})
    for g in com.get("registers", []):
        d = dict(g["def"])
        d.update({"status": "watch", "added": today, "by": "위원회 합의"})
        R["factors"][g["key"]] = d
    R.setdefault("committee_log", []).append({"date": today, "level": com.get("level"), "version": by_version,
                                              "adds": [(a["key"], a["weight"]) for a in com.get("adds", [])],
                                              "removes": [x["key"] for x in com.get("removes", [])],
                                              "registers": [g["key"] for g in com.get("registers", [])],
                                              "rejected": com.get("rejected", [])[:20], "summary": com.get("summary", "")})
    FA.save(R)


def cmd_apply(path):
    df = load_df()
    W = WM.load()
    cur = WM.current(W)
    dec = json.load(open(path, encoding="utf-8"))
    level = dec.get("level")
    if level not in W["rules"]["levels"]:
        sys.exit(f"결정 파일의 level '{level}'이 없습니다 — weekly | monthly | quarterly")
    today = today_kst().isoformat()
    by = dec.get("by") or (W["rules"].get("decider") or {}).get("name") or "Claude"
    _, w = wind_series(df, W=W)
    chk = check_summary(direction_check(df, w))
    note = (dec.get("direction_note") or "").strip()
    com = committee_result(level)
    changes = bool(com.get("adds") or com.get("removes"))
    sched = W["rules"].setdefault("schedule", {})
    sched.pop("in_progress", None)
    if dec.get("decision") == "유지":
        if changes:
            sys.exit("위원회가 팩터 넣기·빼기를 합의했으므로 '유지'가 아니라 '변경'(합의 반영)이어야 합니다")
        if not (dec.get("summary") or "").strip():
            sys.exit("유지 결정에도 summary(이유)가 필요합니다")
        W.setdefault("reviews", []).append({"date": today, "level": level, "by": by, "decision": "유지", "version": cur["v"],
                                            "summary": dec["summary"].strip(), "direction_note": note, "check": chk,
                                            "committee": com.get("summary") or None})
        set_next(W, today)
        json.dump(W, open(WM.PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        if com.get("registers") or com.get("date"):
            apply_committee(com, None, today, cur["v"])
        print(json.dumps({"applied": "유지", "level": level, "version": cur["v"], "registered": [g["key"] for g in com.get("registers", [])]}, ensure_ascii=False))
        return
    ok, errs, new = check(dec, cur, W["rules"], level, com)
    if not ok:
        print(json.dumps({"applied": False, "오류": errs}, ensure_ascii=False, indent=1))
        sys.exit(1)
    start = next_trading_day(df.index[-1].date()).strftime("%Y-%m-%d")
    nv = {"tc": new["tc"], "lq": new["lq"], "wind": new["wind"]}
    if com.get("adds"):
        df = load_df([a["key"] for a in com["adds"]])
    a, b = headline(composite_eval(df, cur)), headline(composite_eval(df, nv))
    v = {"v": cur["v"] + 1, "from": start, "set": today, "level": level, "by": by, "summary": dec["summary"].strip(),
         "tc": new["tc"], "lq": new["lq"], "wind": new["wind"], "reasons": dec.get("reasons") or {},
         "evidence": {"이전": a, "새": b}}
    if com.get("adds") or com.get("removes"):
        v["factors"] = {"added": [{"key": x["key"], "group": x["group"], "weight": x["weight"]} for x in com.get("adds", [])],
                        "removed": [{"key": x["key"], "group": x["group"]} for x in com.get("removes", [])],
                        "committee": com.get("summary", "")}
    if v["from"] <= cur["from"]:  # 같은 날 두 번 바꾸면 앞 버전을 대신한다
        v["from"] = cur["from"]
    W["versions"].append(v)
    W.setdefault("reviews", []).append({"date": today, "level": level, "by": by, "decision": "변경", "version": v["v"], "from": v["from"],
                                        "summary": v["summary"], "direction_note": note, "check": chk,
                                        "committee": com.get("summary") or None})
    set_next(W, today)
    json.dump(W, open(WM.PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    if com.get("date"):
        apply_committee(com, v["from"], today, v["v"])
    print(json.dumps({"applied": "변경", "level": level, "version": v["v"], "from": v["from"],
                      "added": [x["key"] for x in com.get("adds", [])], "removed": [x["key"] for x in com.get("removes", [])],
                      "registered": [g["key"] for g in com.get("registers", [])]}, ensure_ascii=False))


def due(d):
    """그날 점검 단계. 이미 그날 점검했거나 다른 세션이 진행 중이면 done."""
    W = WM.load()
    iso = d.isoformat()
    if any(r.get("date") == iso for r in W.get("reviews", [])) or (W["rules"].get("schedule") or {}).get("in_progress") == iso:
        return "done"
    return level_of(d) or "no"


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a or a[0] not in ("brief", "test", "apply", "due"):
        sys.exit(__doc__)
    if a[0] == "due":
        d = dt.date.fromisoformat(a[1]) if len(a) > 1 else today_kst()
        print(due(d))
    elif a[0] == "brief":
        cmd_brief(a[1] if len(a) > 1 else (level_of(today_kst()) or "weekly"))
    elif a[0] == "test":
        cmd_test(a[1])
    else:
        cmd_apply(a[1])
