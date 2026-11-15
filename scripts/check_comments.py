"""Fable이 쓴 코멘트를 검사한다.  (작업 담당 Opus가 실행)

python3 scripts/check_comments.py <날짜> [--file 다른경로.json]
  - 오류(errors): 형식이 틀려 화면이 깨지거나 빠지는 것 → 반드시 고친다
  - 경고(warnings): 길이 초과, 단정적 표현, 자료 묶음에서 찾을 수 없는 숫자 → Fable에게 확인시킨다
종료 코드: 오류 있으면 1, 없으면 0. 결과는 JSON 한 덩어리로 출력.

숫자 대조: 코멘트 속 숫자를 data/raw/brief_<날짜>.json(자료 묶음, research 포함)의 숫자와 맞춰 본다.
반올림·부호·%/bp 환산까지는 같은 값으로 본다. 두 값으로 계산한 값(예: 453÷75≈6배)은 경고로 나올 수 있으니
Fable이 근거를 확인하고 남길지 정한다.
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")

TONES = {"up", "down", "flat"}
FEAT_KEYS = ["tag", "bm", "e1", "e2", "point", "caution"]
LIMITS = {  # 화면에서 넘치지 않게 (글자 수, 넘으면 경고)
    "wind.headline": 80, "market.headline": 60, "point.h": 32, "point.t": 230,
    "card.tag": 12, "card.title": 26, "card.num": 26, "card.back": 230,
    "tc_summary": 170, "lq_summary": 170, "quad": 260, "feature": 40, "feature.tag": 14,
}
STRONG = ["매수하세요", "매도하세요", "사세요", "파세요", "사야 합니다", "팔아야 합니다", "무조건", "반드시 오", "확실히 오",
          "확실히 내", "추천합니다", "지금 당장", "올인", "finviz", "Finviz"]
NAMES = ["S&P500", "S&P 500", "나스닥100", "나스닥 100", "다우30", "코스피200", "M2", "10년물", "2년물", "200일선", "50일선",
         "20일선", "200일", "50일", "20일", "RSI(14일)", "RSI(14)", "FY", "1~5"]


def walk_strings(o, path=""):
    if isinstance(o, str):
        yield path, o
    elif isinstance(o, dict):
        for k, v in o.items():
            yield from walk_strings(v, f"{path}.{k}" if path else k)
    elif isinstance(o, list):
        for j, v in enumerate(o):
            yield from walk_strings(v, f"{path}[{j}]")


def walk_numbers(o):
    if isinstance(o, bool):
        return
    if isinstance(o, (int, float)):
        yield float(o)
    elif isinstance(o, str):
        for x in nums_in(o, keep_small=True):
            yield x[0]
    elif isinstance(o, dict):
        for k, v in o.items():
            yield from walk_numbers(k) if isinstance(k, str) and re.search(r"\d", k) else iter(())
            yield from walk_numbers(v)
    elif isinstance(o, list):
        for v in o:
            yield from walk_numbers(v)


NUM = re.compile(r"(?<![A-Za-z&\d.])[-−+]?\$?(\d{1,3}(?:,\d{3})+|\d+)(\.\d+)?")


def nums_in(text, keep_small=False):
    t = text
    for n in NAMES:
        t = t.replace(n, " ")
    t = re.sub(r"\d{1,2}/\d{1,2}", " ", t)                 # 날짜 11/13
    t = re.sub(r"\d{1,2}:\d{2}", " ", t)                    # 시각
    t = re.sub(r"(?<![\d,.])(19|20)\d{2}(?![\d,.])", " ", t)  # 연도 2026
    t = re.sub(r"\d+\s*(?:개월|거래일|주\s*(?:뒤|전|연속|째|간|동안|이동)|분기|번째|위\b|등\b|단계|일\s*연속|일째|년\s*만)", " ", t)
    t = re.sub(r"\d+Q|Q\d+|\d+H\b", " ", t)                   # 3Q, Q3
    out = []
    for m in NUM.finditer(t):
        whole, frac = m.group(1).replace(",", ""), m.group(2) or ""
        x = float(whole + frac)
        d = len(frac) - 1 if frac else 0
        if not keep_small and d == 0 and x <= 12:
            continue
        out.append((x, d, m.start()))
    return out


def matches(x, d, pool):
    for c in pool:
        for y in (c, c * 100, c / 100, c / 1000, c / 1e6, c * 10):  # %·bp·억·조 환산
            if round(abs(y), d) == x:
                return True
    return False


def main():
    if len(sys.argv) < 2:
        sys.exit("사용법: check_comments.py <날짜> [--file 경로]")
    date = sys.argv[1]
    path = sys.argv[sys.argv.index("--file") + 1] if "--file" in sys.argv else os.path.join(DATA, "comments", f"{date}.json")
    errors, warns = [], []
    try:
        cm = json.load(open(path, encoding="utf-8"))
    except (OSError, ValueError) as e:
        print(json.dumps({"ok": False, "errors": [f"JSON을 읽을 수 없음: {e}"], "warnings": []}, ensure_ascii=False))
        sys.exit(1)
    board = None
    try:
        board = json.load(open(os.path.join(DATA, "board", f"{date}.json"), encoding="utf-8"))
    except (OSError, ValueError):
        pass
    brief = {}
    try:
        brief = json.load(open(os.path.join(DATA, "raw", f"brief_{date}.json"), encoding="utf-8"))
    except (OSError, ValueError):
        warns.append("자료 묶음(brief)이 없어 숫자 대조를 못 함")

    def need_str(obj, key, where, lim=None):
        v = obj.get(key) if isinstance(obj, dict) else None
        if not isinstance(v, str) or not v.strip():
            errors.append(f"{where}.{key} 없음/빈 값")
            return ""
        if lim and len(v) > lim:
            warns.append(f"{where}.{key} {len(v)}자 (권장 {lim}자 이하)")
        return v

    def points(key, n=3):
        P = cm.get(key)
        if not isinstance(P, list) or len(P) != n:
            errors.append(f"{key}: {n}개 {{h,t}} 목록이어야 함")
            return
        for j, p in enumerate(P):
            need_str(p, "h", f"{key}[{j}]", LIMITS["point.h"])
            need_str(p, "t", f"{key}[{j}]", LIMITS["point.t"])

    if cm.get("date") != date:
        errors.append(f"date가 {date}가 아님 ({cm.get('date')})")
    W = cm.get("wind") or {}
    need_str(W, "headline", "wind", LIMITS["wind.headline"])
    if not isinstance(W.get("points"), list) or len(W.get("points")) != 3:
        errors.append("wind.points: 3개 {h,t} 목록이어야 함")
    else:
        for j, p in enumerate(W["points"]):
            need_str(p, "h", f"wind.points[{j}]", LIMITS["point.h"])
            need_str(p, "t", f"wind.points[{j}]", LIMITS["point.t"])
    M = cm.get("market") or {}
    mh = need_str(M, "headline", "market", LIMITS["market.headline"])
    if cm.get("oneliner") != mh:
        errors.append("oneliner는 market.headline과 같아야 함")
    cards = M.get("cards")
    if not isinstance(cards, list) or not 4 <= len(cards) <= 5:
        errors.append("market.cards: 4~5장이어야 함")
    else:
        for j, cd in enumerate(cards):
            if cd.get("tone") not in TONES:
                errors.append(f"market.cards[{j}].tone은 up/down/flat 중 하나")
            for k in ("tag", "title", "num", "back"):
                need_str(cd, k, f"market.cards[{j}]", LIMITS[f"card.{k}"])
    for k in ("tc_summary", "lq_summary", "quad"):
        need_str(cm, k, "", LIMITS[k])
    for k in ("tc", "lq"):
        need_str(cm, k, "")
    points("tc_points")
    points("lq_points")
    F = cm.get("features")
    want = [r["t"] for r in (board or {}).get("features") or []]
    if want:
        if not isinstance(F, dict):
            errors.append("features 없음")
        else:
            for t in want:
                if t not in F:
                    errors.append(f"features.{t} 없음 (대표 신고가)")
            for t, e in F.items():
                if t not in want:
                    warns.append(f"features.{t}: 오늘 대표 신고가가 아님")
                    continue
                for k in FEAT_KEYS:
                    need_str(e, k, f"features.{t}", LIMITS["feature.tag" if k == "tag" else "feature"])

    # 회사 설명 누락
    notes = {}
    try:
        notes = json.load(open(os.path.join(DATA, "notes", "companies.json"), encoding="utf-8"))
    except (OSError, ValueError) as e:
        errors.append(f"companies.json을 읽을 수 없음: {e}")
    miss = []
    for key in ("features", "top40", "gainers", "losers", "mega"):
        for r in (board or {}).get(key) or []:
            if not (notes.get(r["t"]) or {}).get("desc") and r["t"] not in miss:
                miss.append(r["t"])
    if miss:
        warns.append("회사 설명 없음: " + ", ".join(miss))

    # 단정적 표현
    for p, s in walk_strings(cm):
        for w in STRONG:
            if w in s:
                warns.append(f"{p}: '{w}' — 단정적 지시/표기 금지 표현")

    # 숫자 대조
    unverified = []
    if brief:
        pool = set(walk_numbers(brief))
        for p, s in walk_strings(cm):
            if p in ("date", "author"):
                continue
            for x, d, pos in nums_in(s):
                if not matches(x, d, pool):
                    ctx = s[max(0, pos - 14): pos + 16].replace("\n", " ")
                    unverified.append(f"{p}: {x:g} … '{ctx}'")
    if unverified:
        warns.append(f"자료 묶음에서 찾지 못한 숫자 {len(unverified)}개 (계산값이면 근거 확인, 아니면 고치거나 삭제)")
    rep = {"ok": not errors, "file": os.path.relpath(path, ROOT), "errors": errors, "warnings": warns, "unverified_numbers": unverified}
    print(json.dumps(rep, ensure_ascii=False, indent=1))
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
