"""날짜별 기록 데이터베이스(CSV)를 만든다.  (작업 담당 Opus가 매일 커밋 전에 실행)

python3 scripts/export_db.py  →  data/db.csv  (사이트에서 https://hangseokemail-spec.github.io/seoks/data/db.csv 로 공개)

구글 시트 "Seoks 날짜별 기록"의 DB 탭이 =IMPORTDATA(위 주소)로 이 파일을 읽고,
'날짜로 보기' 탭에서 날짜를 고르면 그날의 숫자·총평·코멘트가 한 화면에 나온다.
한 줄 = 미국 거래일 하루 (최신이 맨 위). 풍향계가 계산되는 2023-09 이후만.
"""
import csv
import datetime as dt
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
SITE = "https://hangseokemail-spec.github.io/seoks/"
DOW = "월화수목금토일"
TONE = {"up": "좋음", "down": "나쁨", "flat": "중립"}


def load(p, default=None):
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def clean(x):
    if x is None:
        return ""
    if isinstance(x, float):
        return round(x, 3)
    return str(x).replace("\r", " ").replace("\n", " ").strip()


def label(v, cuts):
    if v is None:
        return ""
    for lo, nm in cuts:
        if v >= lo:
            return nm
    return cuts[-1][1]


TC_CUT = [(4.5, "광기"), (3.5, "과열"), (2.5, "중립"), (1.5, "불안"), (-9, "공포")]
LQ_CUT = [(4.5, "풍부"), (3.5, "우호"), (2.5, "중립"), (1.5, "긴축"), (-9, "경색")]
W_CUT = [(70, "강한 순풍"), (55, "순풍"), (45, "무풍"), (30, "역풍"), (-9, "강한 역풍")]
W_ACT = {"강한 순풍": "적극", "순풍": "우호", "무풍": "관망", "역풍": "조심", "강한 역풍": "매우 조심"}

COLS = ["날짜", "풍향계", "풍향계 구간", "행동 힌트", "총평", "새로 사기", "갖고 있는 주식", "조심할 것", "오늘 한 줄",
        "S&P500", "S&P500 등락%", "나스닥100", "나스닥100 등락%", "나스닥종합 등락%", "다우 등락%", "코스피", "코스피 등락%",
        "VIX", "달러인덱스", "미 10년물%", "트렌드캐치", "트렌드캐치 판단", "유동성", "유동성 판단", "1주 전 풍향계",
        "오른 종목", "내린 종목", "52주 신고가", "52주 신저가", "미국전체 50일선 위%", "미국전체 200일선 위%",
        "S&P500 50일선 위%", "S&P500 200일선 위%",
        "시장 한 줄", "시장의 변화 카드", "핵심 코멘트 1", "핵심 코멘트 2", "핵심 코멘트 3", "앞으로 이렇게 되면",
        "트렌드캐치 종합의견", "트렌드캐치 코멘트", "유동성 종합의견", "유동성 코멘트", "판단 보조(사분면)",
        "대표 신고가", "대표 신고가 설명", "사이트에서 보기", "가중치 버전"]


def pts(arr):
    out = []
    for p in arr or []:
        if isinstance(p, str):
            out.append(p)
        else:
            t = TONE.get(p.get("tone"))
            out.append(f"{'[' + t + '] ' if t else ''}{p.get('h', '')} — {p.get('t', '')}")
    return out


def main():
    s = load(os.path.join(DATA, "series.json"))
    wind = load(os.path.join(DATA, "wind.json"), {})
    bh = load(os.path.join(DATA, "hist", "breadth.json"), {})
    a50 = load(os.path.join(DATA, "hist", "sp500_a50.json"), {})
    a200 = load(os.path.join(DATA, "hist", "sp500_a200.json"), {})
    dates, c = s["dates"], s["cols"]
    widx = {d: k for k, d in enumerate(wind.get("dates") or [])}
    vers = (load(os.path.join(DATA, "weights.json"), {}) or {}).get("versions") or []
    def ver(d):
        v = None
        for x in vers:
            if x["from"] <= d:
                v = x
        return f"v{v['v']} (심리 {round(v['wind']['sent'] * 100)}%)" if v else ""
    col = lambda k, i: (c.get(k) or [None] * len(dates))[i] if i >= 0 else None
    chg = lambda k, i: round((col(k, i) / col(k, i - 1) - 1) * 100, 2) if i > 0 and col(k, i) and col(k, i - 1) else None
    rows = []
    for i, d in enumerate(dates):
        if d not in widx or wind["w"][widx[d]] is None:
            continue
        w = wind["w"][widx[d]]
        k0 = widx[d] - 5
        w0 = wind["w"][k0] if k0 >= 0 else None
        zone = label(w, W_CUT) if w is not None else ""
        cm = load(os.path.join(DATA, "comments", f"{d}.json"), {}) or {}
        wc = cm.get("wind") or {}
        g = wc.get("guide") or {}
        mk = cm.get("market") or {}
        P = pts(wc.get("points"))
        b = bh.get(d) or {}
        F = cm.get("features") or {}
        cards = " | ".join(f"[{TONE.get(x.get('tone'), '')}] {x.get('title', '')}: {x.get('num', '')} — {x.get('back', '')}" for x in mk.get("cards") or [])
        scen = " | ".join(f"[{TONE.get(x.get('tone'), '')}] 만약 {x.get('if', '')} → {x.get('then', '')}" for x in wc.get("scenarios") or [])
        tc, lq = col("tc", i), col("lq", i)
        wd = DOW[dt.date.fromisoformat(d).weekday()]
        rows.append([f"{d} ({wd})", w, zone, W_ACT.get(zone, ""), wc.get("verdict"), g.get("buy"), g.get("hold"), g.get("watch"),
                     wc.get("headline") or cm.get("oneliner"),
                     col("spx", i), chg("spx", i), col("ndx", i), chg("ndx", i), chg("ixic", i), chg("dji", i), col("kospi", i), chg("kospi", i),
                     col("vix", i), col("dxy", i), col("us10y", i), tc, label(tc, TC_CUT) if tc is not None else "", lq, label(lq, LQ_CUT) if lq is not None else "", w0,
                     b.get("adv"), b.get("dec"), b.get("nh"), b.get("nl"), b.get("above50"), b.get("above200"),
                     a50.get(d, b.get("sp500_above50")), a200.get(d, b.get("sp500_above200")),
                     mk.get("headline") or cm.get("oneliner"), cards, P[0] if len(P) > 0 else "", P[1] if len(P) > 1 else "", P[2] if len(P) > 2 else "", scen,
                     cm.get("tc_summary") or cm.get("tc"), " | ".join(pts(cm.get("tc_points"))), cm.get("lq_summary") or cm.get("lq"), " | ".join(pts(cm.get("lq_points"))),
                     cm.get("quad"),
                     ", ".join(f"{t}({F[t].get('tag', '')})" for t in F),
                     " | ".join(f"{t}: {F[t].get('bm', '')} · {F[t].get('e1', '')} · {F[t].get('e2', '')} · 포인트 {F[t].get('point', '')} · 주의 {F[t].get('caution', '')}" for t in F),
                     f"{SITE}?tab=wind&date={d}", ver(d)])
    rows.reverse()
    out = os.path.join(DATA, "db.csv")
    with open(out, "w", encoding="utf-8", newline="") as f:
        wr = csv.writer(f)
        wr.writerow(COLS)
        for r in rows:
            wr.writerow([clean(x) for x in r])
    print(json.dumps({"db": "data/db.csv", "rows": len(rows), "first": rows[0][0] if rows else None, "last": rows[-1][0] if rows else None,
                      "with_comments": sum(1 for r in rows if r[4] or r[33]), "bytes": os.path.getsize(out)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
