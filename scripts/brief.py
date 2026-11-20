"""해석·편집 담당(Fable)에게 넘길 '자료 묶음'을 만든다.  (작업 담당 Opus가 실행)

python3 scripts/brief.py [YYYY-MM-DD]
  → data/raw/brief_<날짜>.json  (data/raw 는 .gitignore 대상이라 커밋되지 않음)

들어가는 것: 그날 현황판(board)·트렌드캐치·유동성·풍향계·예측력 요약·웹 지표 최신값,
대표 신고가의 이전 코멘트(재사용 후보), 회사 설명이 없는 종목,
그리고 Opus가 웹에서 확인해 적은 사실 data/raw/research_<날짜>.json (있으면 그대로 포함).
Fable은 이 파일에 있는 사실·숫자만 써서 코멘트를 쓴다.
"""
import datetime as dt
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import weights as WM  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
RAW = os.path.join(DATA, "raw")

TC_ITEMS = [  # key, 이름, 기준일 키(latest.asof / series obs_*), 단위
    ("fg", "공포탐욕(CNN Fear & Greed)", "fg", ""),
    ("aaii", "AAII 강세−약세 스프레드", "aaii", "%p"),
    ("vix", "VIX", None, ""),
    ("hy", "하이일드 스프레드", "hy", "%"),
    ("pc", "Put/Call 비율", "pc", ""),
    ("margin", "신용융자 YoY", "margin", "%"),
    ("a200", "S&P500 200일선 위 비율", None, "%"),
    ("rsi", "RSI(14일, SPY)", None, ""),
    ("dev", "200일선 이격도(SPY)", None, "%"),
]
LQ_ITEMS = [  # key, 카테고리, 가중치, 이름, 기준일 키, 단위
    ("fed", "A", 14, "연준 총자산 3개월 변화", "fed", "%"),
    ("nl", "A", 14, "순유동성 3개월 변화", "nl", "%"),
    ("m2", "A", 7, "M2 통화량 YoY", "m2", "%"),
    ("effr", "B", 10, "기준금리(EFFR) 3개월 변화", "effr", "%p"),
    ("hy", "B", 8.75, "하이일드 스프레드", "lq_hy", "%"),
    ("dxy", "B", 6.25, "달러인덱스 6개월 변화", None, "%"),
    ("margin", "C", 10, "신용융자 YoY", "margin", "%"),
    ("bank", "C", 10, "상업은행 신용 YoY", "bank", "%"),
    ("vol", "D", 5.33, "거래량(20일 평균 대비)", None, "%"),
    ("nfci", "D", 8, "NFCI 금융여건지수", "nfci", ""),
    ("y10", "D", 6.67, "미 국채 10년물 금리", "us10y", "%"),
]
LQ_CAT = {"A": "돈의 양", "B": "돈의 값", "C": "돈의 쓰임", "D": "돈의 흐름"}
TC_LABELS = {5: "광기", 4: "과열", 3: "중립", 2: "불안", 1: "공포"}
LQ_LABELS = {5: "풍부", 4: "우호", 3: "중립", 2: "긴축", 1: "경색"}
TC_ACTION = {"광기": "분할 매도", "과열": "매도 준비", "중립": "매매 보류", "불안": "분할 매수", "공포": "적극 매수(장기)"}

RULES = {
    "트렌드캐치_구간": "4.5~5 광기(분할 매도) · 3.5~4.5 과열(매도 준비) · 2.5~3.5 중립(매매 보류) · 1.5~2.5 불안(분할 매수) · 1~1.5 공포(적극 매수). 점수가 높을수록 탐욕(역발상으로 읽음)",
    "유동성_구간": "4.5~5 풍부 · 3.5~4.5 우호 · 2.5~3.5 중립 · 1.5~2.5 긴축 · 1~1.5 경색",
    "풍향계_구간": "0~30 강한 역풍(매우 조심) · 30~45 역풍(조심) · 45~55 무풍(관망) · 55~70 순풍(우호) · 70~100 강한 순풍(적극)",
    "10년물_점수": "13주 변화 ≤−40bp 5 / −40~−10 4 / ±10 3 / +10~+40 2 / ≥+40 1, 금리 4.5% 이상이면 −1점",
    "달러6개월_점수": "≤−5% 5 / −5~−2 4 / ±2 3 / +2~+5 2 / ≥+5% 1",
    "EFFR_점수": "−0.5%p 이하 5 / −0.5~−0.1 4 / ±0.1 3 / +0.1~+0.5 2 / ≥+0.5 1",
    "트렌드캐치_지표구간": {
        "공포탐욕": "76~100 5 / 56~75 4 / 45~55 3 / 25~44 2 / 0~24 1",
        "AAII": ">30 5 / 20~30 4 / −20~20 3 / −30~−20 2 / <−30 1",
        "VIX": "<15 5 / 15~20 4 / 20~30 3 / 30~40 2 / >40 1",
        "하이일드": "≤3% 5 / 3~4% 4 / 4~5% 3 / 5~7% 2 / >7% 1",
        "Put/Call": "<0.4 5 / 0.4~0.5 4 / 0.5~1.0 3 / 1.0~1.2 2 / >1.2 1",
        "신용융자YoY": ">40% 5 / 20~40% 4 / −20~20% 3 / −30~−20% 2 / <−30% 1",
        "200일선위비율": ">70% 5 / 60~70% 4 / 30~60% 3 / 20~30% 2 / <20% 1",
        "RSI": ">70 5 / 60~70 4 / 30~60 3 / 20~30 2 / <20 1",
        "이격도": ">15% 5 / 10~15% 4 / −10~10% 3 / −15~−10% 2 / <−15% 1",
    },
    "시장체력_기준": "미국 상장 주식(ETF 제외) 전체 / S&P500 503종목. 50·200일선 위 비율 80% 이상 과열권, 20% 이하 바닥권",
}


def load(p, default=None):
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def label(v, table):
    if v is None:
        return None
    return table[max(1, min(5, int(round(v + 1e-9))))]


def zone(v):
    if v is None:
        return None
    for lo, name in ((70, "강한 순풍"), (55, "순풍"), (45, "무풍"), (30, "역풍"), (0, "강한 역풍")):
        if v >= lo:
            return name


def ind_ko():
    """assets/meta.js 의 IND_KO(산업 한글명)를 읽는다. 화면과 같은 이름을 쓰기 위해."""
    try:
        js = open(os.path.join(ROOT, "assets", "meta.js"), encoding="utf-8").read()
        blk = js[js.index("const IND_KO"):]
        blk = blk[:blk.index("};")]
        return dict(re.findall(r'"([^"]+)":\s*"([^"]+)"', blk))
    except ValueError:
        return {}


def explain_zones():
    """assets/meta.js 의 EXPLAIN.zones(역풍·순풍 구간별 뜻·행동 기준)를 읽는다. 화면과 같은 기준을 쓰기 위해."""
    try:
        js = open(os.path.join(ROOT, "assets", "meta.js"), encoding="utf-8").read()
        blk = js[js.index("zones: {", js.index("const EXPLAIN")):]
        blk = blk[:blk.index("\n    },")]
        out = {}
        for nm, body in re.findall(r'"([^"]+)":\s*\{([^}]*)\}', blk):
            out[nm] = dict(re.findall(r'(\w+):\s*"([^"]*)"', body))
        return out
    except ValueError:
        return {}


def zone_stats(corr, kind, label):
    """지금 점수 구간일 때 과거 N주 뒤 지수 성적 (corr.json 구간별 막대와 같은 값)."""
    out = {}
    for ix, nm in (("spx", "S&P500"), ("ndx", "나스닥100"), ("kospi", "코스피")):
        cr = ((corr or {}).get(kind) or {}).get(ix) or {}
        for h, hn in (("1", "1주뒤"), ("4", "4주뒤"), ("12", "12주뒤")):
            bk = (cr.get("buckets") or {}).get(h) or {}
            tn = sum(r["n"] for r in bk.values())
            avg = round(sum(r["mean"] * r["n"] for r in bk.values()) / tn, 2) if tn else None
            cur = bk.get(label)
            out[f"{nm}_{hn}"] = {"지금구간": label, "평균%": cur and cur["mean"], "오른비율%": cur and cur["win"], "표본_주": cur and cur["n"],
                                "전체평균%": avg, "순위상관": (cr.get("ic") or {}).get(h)}
    return out


def main():
    latest = load(os.path.join(DATA, "latest.json"), {})
    date = sys.argv[1] if len(sys.argv) > 1 else latest.get("date")
    s = load(os.path.join(DATA, "series.json"))
    dates, c = s["dates"], s["cols"]
    if date not in dates:
        sys.exit(f"series.json 에 {date} 가 없습니다")
    i = dates.index(date)
    iw = max(0, i - 5)
    v = lambda k, j=i: (c.get(k) or [None] * len(dates))[j]
    asof = latest.get("asof", {})
    board = load(os.path.join(DATA, "board", f"{date}.json"))
    wind = load(os.path.join(DATA, "wind.json"), {})
    ana = load(os.path.join(DATA, "analysis.json"), {})
    manual = load(os.path.join(DATA, "manual.json"), {})
    notes = load(os.path.join(DATA, "notes", "companies.json"), {})
    hist = load(os.path.join(DATA, "hist", "breadth.json"), {})
    KO = ind_ko()

    # 트렌드캐치·유동성 지표
    def a13(key):
        it = (ana.get("items") or {}).get(key) or {}
        r = it.get("spx")
        if not r:
            return None
        return {"ic_13주뒤_S&P500": (r.get("ic") or {}).get("13"), "유의": (r.get("sig") or {}).get("13"),
                "지난13주_반영": r.get("past13"), "역할": r.get("role"), "방향": r.get("direction"), "시작": r.get("start")}

    CW = WM.current()
    wtc, wlq = WM.norm(CW["tc"]), WM.norm(CW["lq"])
    fstr, (fa, fb, fc) = WM.formula(CW)
    RULES["풍향계_식"] = f"{fstr} (= 심리 바람 {CW['wind']['sent'] * 100:.0f}% + 유동성 바람 {(1 - CW['wind']['sent']) * 100:.0f}%, 가중치 버전 v{CW['v']} · {CW['from']}부터)"
    tc_items = [{"key": k, "이름": n, "가중치%": round(wtc.get(k, 0), 1), "값": v(f"tc_{k}"), "점수": v(f"s_tc_{k}"), "점수_1주전": v(f"s_tc_{k}", iw),
                 "기준일": (v(f"obs_{k}") or asof.get(ak)) if ak else date, "단위": u, "예측력": a13(f"tc_{k}")}
                for k, n, ak, u in TC_ITEMS]
    lq_items = [{"key": k, "카테고리": f"{cat} {LQ_CAT[cat]}", "가중치": round(wlq.get(k, 0), 2), "이름": n, "값": v(f"lq_{k}"), "점수": v(f"s_lq_{k}"),
                 "점수_1주전": v(f"s_lq_{k}", iw), "기준일": asof.get(ak) if ak else date, "단위": u, "예측력": a13(f"lq_{k}")}
                for k, cat, w, n, ak, u in LQ_ITEMS]
    # 위원회가 넣은 새 팩터(data/factors.json active) — 점수는 '최근 3년 중 위치 5등분'
    import factors as FA
    FR = FA.load()
    for k in FA.keys(FR):
        f = FR["factors"][k]
        g = f["group"]
        it = {"key": k, "이름": f["name"], "새_팩터": True, "값": v(f"{g}_{k}"), "점수": v(f"s_{g}_{k}"), "점수_1주전": v(f"s_{g}_{k}", iw),
              "기준일": asof.get(k) or date, "단위": f.get("unit", ""), "점수_방식": "그날까지 공개된 최근 3년 값 중 위치를 5등분(1~5)", "왜_넣었나": f.get("why")}
        if g == "tc":
            tc_items.append({**it, "가중치%": round(wtc.get(k, 0), 1)})
        else:
            lq_items.append({**it, "카테고리": f"{f.get('cat') or 'E'} {LQ_CAT.get(f.get('cat') or 'E', '경기·물가')}", "가중치": round(wlq.get(k, 0), 2)})
    for it in tc_items + lq_items:
        if (it.get("가중치%") if "가중치%" in it else it.get("가중치")) == 0:
            it["메모"] = "위원회 합의로 뺀 지표 — 종합 점수에 들어가지 않음"
    extra = {"10년물_13주변화_bp": v("lq_y10_chg"), "EFFR_수준": v("lq_effr_level"), "순유동성_수준_십억달러": v("lq_nl_level")}
    cats = {}
    for it in lq_items:
        if it["점수"] is not None:
            cats.setdefault(it["카테고리"], []).append((it["점수"], it["가중치"]))
    cat_avg = {k: round(sum(a * b for a, b in xs) / sum(b for _, b in xs), 2) for k, xs in cats.items()}

    tc, lq, tcw, lqw = v("tc"), v("lq"), v("tc", iw), v("lq", iw)
    wi = (wind.get("dates") or []).index(date) if date in (wind.get("dates") or []) else None
    wv = lambda key, j: (wind.get(key) or [None])[j] if j is not None and j >= 0 else None
    w_now, w_week = wv("w", wi), wv("w", wi - 5 if wi is not None else None)

    # 최근 10거래일 지수 흐름 (일별 등락률)
    recent = []
    for j in range(max(1, i - 9), i + 1):
        row = {"date": dates[j]}
        for k, nm in (("spx", "S&P500"), ("ndx", "나스닥100"), ("ixic", "나스닥종합"), ("dji", "다우")):
            a0, a1 = v(k, j - 1), v(k, j)
            row[nm] = round((a1 / a0 - 1) * 100, 2) if a0 and a1 else None
        row["VIX"] = v("vix", j)
        recent.append(row)

    corr = load(os.path.join(DATA, "corr.json"), {})
    # 시나리오용 경계값: 지금 유동성(트렌드캐치)이 그대로일 때 풍향계 45·55·70·30이 되는 트렌드캐치(유동성) 값
    bounds = None
    if tc is not None and lq is not None:
        bounds = {"설명": f"풍향계 = {fstr}. 한쪽이 그대로일 때 다른 쪽이 이 값이 되면 해당 경계에 닿음",
                  "유동성 그대로일 때 트렌드캐치": {f"풍향계 {w}": round((fa + fc * lq - w) / fb, 2) for w in (30, 45, 55, 70)},
                  "트렌드캐치 그대로일 때 유동성": {f"풍향계 {w}": round((w - fa + fb * tc) / fc, 2) for w in (30, 45, 55, 70)}}

    out = {
        "_안내": "Fable(해석·편집 담당)은 이 파일의 사실·숫자만 사용한다. 여기 없는 원인·실적·뉴스는 쓰지 않는다.",
        "date": date, "date_1주전": dates[iw], "generated": dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M KST"),
        "rules": RULES,
        "풍향계": {"값": w_now, "구간": zone(w_now), "심리바람": wv("sent", wi), "유동성바람": wv("liq", wi),
                 "1주전": w_week, "1주전_구간": zone(w_week),
                 "구간별_60거래일뒤_S&P500": ((wind.get("stats") or {}).get("spx") or {}).get("60"),
                 "구간별_60거래일뒤_나스닥100": ((wind.get("stats") or {}).get("ndx") or {}).get("60"),
                 "이후_순위상관_S&P500": ((wind.get("lead") or {}).get("spx") or {}).get("fwd"),
                 "이후_순위상관_나스닥100": ((wind.get("lead") or {}).get("ndx") or {}).get("fwd"),
                 "지난수익률과_순위상관_S&P500": ((wind.get("lead") or {}).get("spx") or {}).get("past"),
                 "검증기간": f"{wind.get('start')} ~ {wind.get('end')}", "거래일_이름": wind.get("hname"),
                 "역풍순풍_행동": explain_zones(), "구간경계_계산": bounds},
        "트렌드캐치": {"값": tc, "판단": label(tc, TC_LABELS), "행동힌트": TC_ACTION.get(label(tc, TC_LABELS)),
                   "1주전": tcw, "반영_지표수": v("tc_n"), "종합_예측력": a13("tc"),
                   "현재구간_과거성적": zone_stats(corr, "tc", label(tc, TC_LABELS)), "지표": tc_items},
        "유동성": {"값": lq, "판단": label(lq, LQ_LABELS), "1주전": lqw, "반영_가중치%": v("lq_w"),
                "카테고리_평균점수": cat_avg, "종합_예측력": a13("lq"),
                "현재구간_과거성적": zone_stats(corr, "lq", label(lq, LQ_LABELS)), "지표": lq_items, "보조값": extra},
        "지수_최근10거래일_일별등락%": recent,
        "웹지표_최신": {k: (manual.get(k) or [None])[-1] for k in ("fg", "aaii", "pc", "margin")},
    }

    if board:
        def tick(r):
            t = r["t"]
            d = {"t": t, "이름": r.get("name"), "섹터": r.get("sector"), "산업": r.get("ind"), "산업_한글": KO.get(r.get("ind")),
                 "국가": r.get("country"), "시총_백만달러": r.get("mcap"), "등락%": r.get("chg"), "S&P500": r.get("sp"),
                 "설명": (notes.get(t) or {}).get("desc") or r.get("desc")}
            if (notes.get(t) or {}).get("bm"):
                d["BM"] = notes[t]["bm"]
            return d

        ix = board.get("indices", {})
        idx = {}
        for k, nm in (("spx", "S&P500"), ("ixic", "나스닥 종합"), ("dji", "다우"), ("ndx", "나스닥100"), ("kospi", "코스피"),
                      ("vix", "VIX"), ("dxy", "달러인덱스"), ("us10y", "미 10년물")):
            r = ix.get(k)
            if not r:
                continue
            sp = r.get("spark") or []
            e = {"이름": nm, "종가": r.get("close"), "등락%": r.get("chg"), "최근6일": sp}
            if k == "us10y":
                e = {"이름": nm, "금리%": r.get("close"), "전일대비_bp": r.get("chg_bp"), "최근6일": sp, "비고": r.get("obs_note")}
            elif len(sp) >= 2 and sp[0]:
                e["5거래일_등락%"] = round((sp[-1] / sp[0] - 1) * 100, 2)
            idx[k] = e
        hd = sorted(d for d in hist if d < date)
        out["현황판"] = {
            "지수": idx,
            "시장체력": board.get("breadth"), "시장체력_전일": hist.get(hd[-1]) if hd else None,
            "섹터_등락": board.get("sector_perf"),
            "강한_산업": [dict(x, 한글=KO.get(x["name"])) for x in board.get("ind_top") or []],
            "약한_산업": [dict(x, 한글=KO.get(x["name"])) for x in board.get("ind_bottom") or []],
            "S&P500_강세주": [tick(r) for r in board.get("gainers") or []],
            "S&P500_약세주": [tick(r) for r in board.get("losers") or []],
            "시총_상위": [tick(r) for r in board.get("mega") or []],
            "신고가_수": board.get("nh_total"), "신고가_S&P500_수": board.get("nh_sp500"),
            "신고가_TOP40_섹터분포": board.get("sectors"),
            "신고가_TOP40": [{"t": r["t"], "섹터": r.get("sector"), "산업_한글": KO.get(r.get("ind")), "등락%": r.get("chg")} for r in board.get("top40") or []],
            "대표_신고가": [tick(r) for r in board.get("features") or []],
        }
        # 대표 신고가: 최근 코멘트에 쓴 내용(재사용 후보, 60일 이내)
        prev = {}
        cdir = os.path.join(DATA, "comments")
        for fn in sorted(os.listdir(cdir), reverse=True) if os.path.isdir(cdir) else []:
            d0 = fn[:-5]
            if d0 >= date or (dt.date.fromisoformat(date) - dt.date.fromisoformat(d0)).days > 60:
                continue
            F = (load(os.path.join(cdir, fn), {}) or {}).get("features") or {}
            for t, e in F.items():
                prev.setdefault(t, dict(e, 작성일=d0))
        out["대표_신고가_이전코멘트"] = {r["t"]: prev[r["t"]] for r in board.get("features") or [] if r["t"] in prev}
        # 회사 설명이 없는 종목
        seen, miss = set(), []
        for key in ("features", "top40", "gainers", "losers", "mega"):
            for r in board.get(key) or []:
                t = r["t"]
                if t in seen:
                    continue
                seen.add(t)
                if not (notes.get(t) or {}).get("desc"):
                    miss.append({"t": t, "이름": r.get("name"), "산업": r.get("ind"), "산업_한글": KO.get(r.get("ind")), "국가": r.get("country")})
        out["회사설명_없음"] = miss
    else:
        out["현황판"] = None

    out["research"] = load(os.path.join(RAW, f"research_{date}.json"))
    os.makedirs(RAW, exist_ok=True)
    path = os.path.join(RAW, f"brief_{date}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(json.dumps({"brief": os.path.relpath(path, ROOT), "풍향계": w_now, "트렌드캐치": tc, "유동성": lq,
                      "대표신고가": len((out.get("현황판") or {}).get("대표_신고가") or []),
                      "이전코멘트_재사용후보": len(out.get("대표_신고가_이전코멘트") or {}),
                      "회사설명_없음": len(out.get("회사설명_없음") or []), "research": out["research"] is not None}, ensure_ascii=False))


if __name__ == "__main__":
    main()
