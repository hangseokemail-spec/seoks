"""작업 지침서(구글 드라이브 'AI › 증시현황판')를 만드는 도구.

python3 scripts/guide_export.py build            → 지침이 바뀌었는지 확인하고, 바뀌었으면 data/raw/guide.html 을 만든다.
                                                   출력(JSON): changed, title, file_ref, folder_id, old_folder_id, prev_doc_id, prev_title_new
python3 scripts/guide_export.py build --force    → 바뀌지 않았어도 새 판을 만든다
python3 scripts/guide_export.py done <문서 id>    → 올린 결과를 data/guide_sync.json 에 기록한다 (그다음 커밋)

원본: GUIDE.md(1부) · DAILY.md(2부) · FABLE.md(3부) · WEIGHTS.md(4부) + data/weights.json 의 현재 가중치·점검 규칙(GUIDE 6절, 자동).
올리는 법은 GUIDE.md 7절.
"""
import datetime as dt
import hashlib
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
RAW = os.path.join(DATA, "raw")
SYNC = os.path.join(DATA, "guide_sync.json")
HTML = os.path.join(RAW, "guide.html")
KST = dt.timezone(dt.timedelta(hours=9))
NAME = "증시현황판 작업 지침서"
PARTS = [("GUIDE.md", "1부. 개요 · 원칙 · 역할 · 일정"), ("DAILY.md", "2부. 매일 아침 작업 절차"),
         ("FABLE.md", "3부. Fable 해석·편집 지침"), ("WEIGHTS.md", "4부. 가중치 점검 (매주 토요일 · 주간/월간/분기)")]
TC = [("fg", "공포탐욕"), ("aaii", "AAII 강세−약세"), ("vix", "VIX"), ("hy", "하이일드 스프레드"), ("pc", "풋콜 비율"),
      ("margin", "신용융자 YoY"), ("a200", "S&P500 200일선 위 비율"), ("rsi", "RSI(14일)"), ("dev", "200일선 이격도")]
LQ = [("fed", "연준 총자산 3개월 변화"), ("nl", "순유동성 3개월 변화"), ("m2", "M2 YoY"), ("effr", "기준금리 3개월 변화"),
      ("hy", "하이일드 스프레드"), ("dxy", "달러 6개월 변화"), ("margin", "신용융자 YoY"), ("bank", "상업은행 신용 YoY"),
      ("vol", "거래량(20일 평균 대비)"), ("nfci", "NFCI 금융여건"), ("y10", "10년물 금리")]
LV = {"weekly": "주간", "monthly": "월간", "quarterly": "분기"}


def read(p):
    with open(os.path.join(ROOT, p), encoding="utf-8") as f:
        return f.read()


def load_sync():
    if os.path.exists(SYNC):
        with open(SYNC, encoding="utf-8") as f:
            return json.load(f)
    return {}


def fmt(x):
    x = round(float(x), 2)
    return str(int(x)) if x == int(x) else f"{x:g}"


def weights_md():
    W = json.loads(read("data/weights.json"))
    v = W["versions"][-1]
    R = W["rules"]
    tot = lambda d, ks: sum(float(d[k]) for k, _ in ks)
    pct = lambda d, ks, k: float(d[k]) / tot(d, ks) * 100
    out = ["## 6. 지금 가중치 (자동으로 실림)", "",
           f"- **버전 {v['v']}** · {v['from']}부터 적용 · 정한 날 {v['set']} · 정한 이: {v.get('by', '')}"
           + (f" · {LV.get(v.get('level'), '')} 점검" if v.get("level") in LV else ""),
           f"- 풍향계 = 심리 **{fmt(v['wind']['sent'] * 100)}%** + 유동성 **{fmt(100 - v['wind']['sent'] * 100)}%**",
           f"- 가중치 결정 모델: {(R.get('decider') or {}).get('name', '')}"]
    if v.get("summary"):
        out += ["", f"> {v['summary']}"]
    FR = json.loads(read("data/factors.json")) if os.path.exists(os.path.join(ROOT, "data/factors.json")) else {"factors": {}}
    names = dict(TC) | dict(LQ) | {k: f["name"] for k, f in FR["factors"].items()}
    for gname, base, grp in (("트렌드캐치", TC, "tc"), ("유동성", LQ, "lq")):
        d = v[grp]
        ks = [k for k, _ in base if k in d] + [k for k in d if k not in dict(base)]
        t = sum(float(d[k]) for k in ks)
        out += ["", f"**{gname} {len(ks)}개**", "", "| 지표 | 가중치 |", "|---|---|"]
        out += [f"| {names.get(k, k)}{' (새 팩터)' if k in FR['factors'] else ''} | {float(d[k]) / t * 100:.2f}% |" for k in ks]
    act = [(k, f) for k, f in FR["factors"].items() if f.get("status") == "active"]
    watch = [(k, f) for k, f in FR["factors"].items() if f.get("status") == "watch"]
    gone = [(k, f) for k, f in FR["factors"].items() if f.get("status") == "removed"]
    out += ["", f"**새 팩터** — 사용 중 {len(act)}개 · 관찰 중인 후보 {len(watch)}개 · 뺀 것 {len(gone)}개 (넣기·빼기는 위원회 합의로만, 4부 8절)"]
    if act:
        out += [f"- 사용 중: " + ", ".join(f"{f['name']}({f.get('activated', '')}부터)" for k, f in act)]
    if watch:
        out += [f"- 관찰 중: " + ", ".join(f"{f['name']}" for k, f in watch)]
    if gone:
        out += [f"- 뺀 것: " + ", ".join(f"{f['name']}({f.get('removed', '')})" for k, f in gone)]
    L = R.get("levels") or {}
    if L:
        out += ["", "**점검 단계별 한도** (지표 하나가 한 번에 움직일 수 있는 폭)", "",
                "| 단계 | 언제 | 트렌드캐치 | 유동성 | 심리 비중 | 그룹당 옮기는 합 | 후보 시험 |", "|---|---|---|---|---|---|---|"]
        when = {"weekly": "나머지 토요일", "monthly": "매달 첫 토요일", "quarterly": "1·4·7·10월 첫 토요일"}
        for k in ("weekly", "monthly", "quarterly"):
            if k in L:
                x = L[k]
                out.append(f"| {LV[k]} | {when[k]} | ±{fmt(x['tc_step'])}%p | ±{fmt(x['lq_step'])}%p | ±{fmt(x['sent_step'] * 100)}%p | "
                           f"{fmt(x['max_turnover'])}%p | {x['후보_시험']}개 |")
        out += ["", f"범위: 트렌드캐치 지표 {R['tc']['min']}~{R['tc']['max']}%, 유동성 지표 {R['lq']['min']}~{R['lq']['max']}%, "
                    f"심리 비중 {fmt(R['wind_sent']['min'] * 100)}~{fmt(R['wind_sent']['max'] * 100)}%. 새 팩터의 최소 가중치 {fmt(R.get('new_min', 0.5))}%. 지표 빼기는 위원회 합의로만."]
    return "\n".join(out)


def compose():
    """지침서 본문(markdown)과 내용 해시. 해시는 날짜·커밋 표시를 빼고 계산한다."""
    parts = []
    for path, title in PARTS:
        s = read(path).strip()
        s = re.sub(r"\A# [^\n]*\n", "", s).strip()  # 원래 맨 위 제목은 부 제목으로 바꾼다
        if path == "GUIDE.md":
            s = re.sub(r"<!-- AUTO:WEIGHTS[^>]*-->", weights_md(), s)
        parts.append(f"# {title}\n\n<p class=\"src\">원본: 저장소 <code>{path}</code></p>\n\n{s}")
    body = "\n\n---\n\n".join(parts)
    return body, hashlib.sha256(body.encode("utf-8")).hexdigest()


def to_html(body, stamp, commit):
    try:
        from markdown_it import MarkdownIt
    except ImportError:  # 예약 작업 세션에 없으면 한 번 설치
        subprocess.run([sys.executable, "-m", "pip", "install", "markdown-it-py", "--break-system-packages", "-q"], check=False)
        from markdown_it import MarkdownIt
    h = MarkdownIt("commonmark", {"html": True}).enable("table").render(body)  # 2~3칸 들여쓴 하위 목록도 그대로
    h = h.replace("<table>", '<table border="1" cellpadding="5" style="border-collapse:collapse">')
    h = h.replace("<pre>", '<pre style="font-family:Consolas,monospace;font-size:9pt;background:#f3f3f3;white-space:pre-wrap">')
    h = h.replace("<code>", '<code style="font-family:Consolas,monospace">')
    h = h.replace("<blockquote>", '<blockquote style="color:#444;border-left:3px solid #aaa;padding-left:8px">')
    head = (f"<h1>{NAME}</h1><p><b>{stamp} 판</b> · 저장소 커밋 <code>{commit}</code> · "
            f"원본은 GitHub 저장소 파일(GUIDE.md · DAILY.md · FABLE.md · WEIGHTS.md · data/weights.json)이며, "
            f"지침이 바뀔 때마다 새 판이 이 폴더에 올라가고 이전 판은 '지난 판' 폴더로 옮겨집니다.</p>"
            f"<p><b>차례</b>: 1부 개요·원칙·역할·일정 · 2부 매일 아침 작업 · 3부 Fable 해석·편집 · 4부 가중치 점검</p><hr>")
    return ('<!DOCTYPE html><html><head><meta charset="utf-8"><title>' + NAME + "</title></head>"
            '<body style="font-family:Arial,\'Malgun Gothic\',sans-serif;font-size:10.5pt;line-height:1.5">'
            + head + h + "</body></html>")


def cmd_build(force=False):
    body, digest = compose()
    S = load_sync()
    changed = force or digest != S.get("hash")
    out = {"changed": changed, "hash": digest[:12], "last_synced": S.get("synced_at"), "folder_id": S.get("folder_id"),
           "old_folder_id": S.get("old_folder_id")}
    if not changed:
        print(json.dumps(out, ensure_ascii=False))
        return
    now = dt.datetime.now(KST)
    stamp = now.strftime("%Y-%m-%d %H:%M")
    try:
        commit = subprocess.run(["git", "-C", ROOT, "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
    except Exception:
        commit = "?"
    os.makedirs(RAW, exist_ok=True)
    html = to_html(body, stamp, commit)
    with open(HTML, "w", encoding="utf-8") as f:
        f.write(html)
    b = html.encode("utf-8")
    out.update({"title": f"{NAME} (최신, {stamp})", "stamp": stamp, "html": HTML, "bytes": len(b),
                "file_ref": f"sha256:{hashlib.sha256(b).hexdigest()}:{HTML}",
                "prev_doc_id": S.get("doc_id"),
                "prev_title_new": f"(지난 판) {NAME} ({S['stamp']})" if S.get("doc_id") and S.get("stamp") else None})
    with open(os.path.join(RAW, "guide_pending.json"), "w", encoding="utf-8") as f:
        json.dump({"hash": digest, "stamp": stamp, "commit": commit}, f, ensure_ascii=False)
    print(json.dumps(out, ensure_ascii=False, indent=1))


def cmd_done(doc_id):
    p = os.path.join(RAW, "guide_pending.json")
    if not os.path.exists(p):
        sys.exit("먼저 build 를 실행하세요 (data/raw/guide_pending.json 없음)")
    with open(p, encoding="utf-8") as f:
        pend = json.load(f)
    S = load_sync()
    if S.get("doc_id"):
        S.setdefault("history", []).append({"doc_id": S["doc_id"], "stamp": S.get("stamp")})
        S["history"] = S["history"][-30:]
    S.update({"doc_id": doc_id, "hash": pend["hash"], "stamp": pend["stamp"], "commit": pend["commit"],
              "synced_at": dt.datetime.now(KST).isoformat(timespec="seconds")})
    with open(SYNC, "w", encoding="utf-8") as f:
        json.dump(S, f, ensure_ascii=False, indent=1)
    os.remove(p)
    print(json.dumps({"recorded": doc_id, "stamp": pend["stamp"]}, ensure_ascii=False))


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a or a[0] not in ("build", "done") or (a[0] == "done" and len(a) < 2):
        sys.exit(__doc__)
    cmd_build("--force" in a) if a[0] == "build" else cmd_done(a[1])
