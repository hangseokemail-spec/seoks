"""새 팩터 위원회 (Fable 2 · Opus 3) — 넣기·빼기·후보 등록은 합의된 안만.  WEIGHTS.md 8절

python3 scripts/committee.py brief <단계>   → data/raw/factor_brief.json (위원이 읽을 근거) — data/raw/committee/ 를 비운다
python3 scripts/committee.py items         → 1라운드 제안(r1_<위원>.json)을 모아 안건 목록 data/raw/committee/items.json
python3 scripts/committee.py tally         → 2라운드 투표(r2_<위원>.json)를 세어 data/raw/committee_result.json (합의된 안만)
python3 scripts/committee.py brief <단계> --register-only   → 임시 위원회(등록만): 넣기·빼기는 하지 않고 새 후보 관찰 등록·자료 요청만 (선생님 지시가 있을 때)
python3 scripts/committee.py apply-register → 임시 위원회 결과의 등록·요청만 data/factors.json에 반영(가중치·점검 기록은 그대로)
근거 자료에는 팩터 도서관(data/factor_library.json: 논문·후보 정의)과 시험실 결과(data/raw/factor_lab.json)가 함께 들어갑니다(오늘 시험 결과가 없으면 brief가 먼저 시험을 돌림).

1라운드 파일 data/raw/committee/r1_<F1|F2|O1|O2|O3>.json:
 {"member": "F1", "model": "Claude Fable 5.2", "summary": "2~4문장",
  "proposals": [{"action": "add", "key": "vixts", "weight": 1.0, "why": "숫자 근거"},
                {"action": "remove", "key": "pc", "group": "tc", "why": "..."},
                {"action": "register", "key": "새키", "def": {팩터 정의 — data/factors.json 형식}, "why": "..."}]}
2라운드 파일 data/raw/committee/r2_<위원>.json:
 {"member": "F1", "votes": {"add:vixts": {"vote": "찬성"|"반대", "weight": 1.0, "why": "..."}, "remove:tc.pc": {...}, "register:새키": {...}}, "summary": "..."}
합의: 넣기·빼기 = 5명 중 4명 이상 찬성, 후보 등록(관찰만) = 3명 이상 찬성. 넣는 가중치 = 찬성한 위원들 가중치의 중앙값(단계 한도 안).
"""
import datetime as dt
import glob
import json
import os
import statistics
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import factor_lab as LAB  # noqa: E402
import factors as FA  # noqa: E402
import weights as WM  # noqa: E402
import weights_eval as E  # noqa: E402

RAW = E.RAW
CDIR = os.path.join(RAW, "committee")
BRIEF = os.path.join(RAW, "factor_brief.json")
RESULT = os.path.join(RAW, "committee_result.json")


def r(x, n=3):
    return E.r(x, n)


def adj(ic, sign):
    return None if ic is None else round(ic * sign, 3)


def long_adj(L, sign):
    if not isinstance(L, dict):
        return L
    out = {"표본(주)": L.get("표본(주)"), "시작": L.get("시작")}
    for k, v in L.items():
        if isinstance(v, dict):
            out[k] = {"맞는방향_강도": adj(v["ic"], sign), "앞절반": adj(v["앞절반"], sign), "뒤절반": adj(v["뒤절반"], sign),
                      "n주": v["n주"], "유의": v["유의"]}
    return out


def redundancy(df, sc, grp, cur, skip=None):
    """2023년 이후 주간: 다른 지표 점수·종합 점수와의 순위상관 상위 3개."""
    wk = E.weekly_idx(df)
    a = sc.iloc[wk]
    rows = []
    for g in ("tc", "lq"):
        for k in WM.keys_of(cur, g):
            if (g, k) == skip:
                continue
            b = df[f"s_{g}_{k}"].iloc[wk].astype(float)
            m = a.notna() & b.notna()
            if m.sum() >= 20 and a[m].nunique() > 1 and b[m].nunique() > 1:
                rows.append((f"{g}.{k}", round(float(a[m].corr(b[m], method="spearman")), 2)))
    rows.sort(key=lambda x: -abs(x[1]))
    comp = df[grp].iloc[wk].astype(float)
    m = a.notna() & comp.notna()
    cc = round(float(a[m].corr(comp[m], method="spearman")), 2) if m.sum() >= 20 and a[m].nunique() > 1 else None
    return {"가장_비슷한_지표": rows[:3], f"{'트렌드캐치' if grp == 'tc' else '유동성'}_종합과": cc}


def effect(df, cur, grp, key, weight, remove=False):
    """넣거나(weight만큼, 나머지를 비례로 줄임) 뺐을 때(나머지에 비례로 나눔) 풍향계 맞는방향_강도 비교."""
    v = json.loads(json.dumps({"tc": cur["tc"], "lq": cur["lq"], "wind": cur["wind"]}))
    d = WM.norm(v[grp])
    if remove:
        d.pop(key, None)
        t = sum(d.values())
        d = {k: x / t * 100 for k, x in d.items()}
    else:
        d = {k: x * (100 - weight) / 100 for k, x in d.items()}
        d[key] = weight
    v[grp] = d
    a, b = E.headline(E.composite_eval(df, cur))["풍향계"], E.headline(E.composite_eval(df, v))["풍향계"]
    return {k: {"지금": a[k], "바꾸면": b[k]} for k in ("spx_20", "spx_60", "ndx_60", "kospi_20", "spx_60_최근52주")}


def library_section():
    """팩터 도서관 + 시험실 결과(위원이 등록 정의를 그대로 가져다 쓸 수 있게)."""
    lab = LAB.OUT
    if not os.path.exists(lab) or json.load(open(lab, encoding="utf-8")).get("date") != E.today_kst().isoformat():
        try:
            LAB.run(save=True)
        except Exception as ex:  # noqa: BLE001
            return {"오류": f"시험실 실행 실패: {str(ex)[:160]}"}
    L = json.load(open(LAB.LIB, encoding="utf-8"))
    o = json.load(open(lab, encoding="utf-8"))
    R = FA.load()
    cands = {}
    for k, c in L["candidates"].items():
        cands[k] = {"이름": c["def"]["name"], "상태": c.get("status"), "이미_등록됨": k in R["factors"],
                    "근거_논문": [L["papers"][p]["cite"] + " — " + L["papers"][p]["finding"] for p in c.get("papers", []) if p in L["papers"]],
                    "메모": c.get("note"), "시험_요약": c.get("lab"), "등록_정의(그대로 register def로 쓸 수 있음)": c["def"]}
    return {"_안내": "팩터 도서관(선생님 지시 2026-11-21: 원자재 비율 등 정확한 수치로 얻을 수 있는 것을 후보로, 고정하지 말고 다양하게, 논문을 찾아 기억했다가 수치로 시험). "
                     "'매수쪽' IC는 클수록 그 신호를 설계한 방향으로 읽었을 때 이후 S&P500을 잘 맞혔다는 뜻입니다(트렌드캐치 후보는 6−점수로 계산). 판정은 참고용입니다.",
            "도서관_규칙": L.get("rules"), "시험_방법": o.get("방법"), "주의": o.get("주의"),
            "기준선_지금_VIX점수(장기)": o.get("기준선_지금_VIX점수(장기)"),
            "시험실_순위(13주IC, 도서관 후보 + 등록된 팩터)": o.get("순위_13주IC"),
            "도서관_후보": cands, "자료_요청(도서관)": L.get("requests"),
            "자세한_결과": os.path.relpath(lab, E.ROOT)}


def cmd_brief(level, register_only=False):
    os.makedirs(CDIR, exist_ok=True)
    for f in glob.glob(os.path.join(CDIR, "*.json")):
        os.remove(f)
    if os.path.exists(RESULT):
        os.remove(RESULT)
    W = WM.load()
    cur = WM.current(W)
    R = FA.load()
    L = W["rules"]["levels"][level]
    FL = L["factors"]
    C = W["rules"]["committee"]
    cand = FA.keys(R, ("watch",))
    df = E.load_df(cand)
    wk = E.weekly_idx(df)
    ana = json.load(open(os.path.join(E.DATA, "analysis.json"), encoding="utf-8"))
    # 후보(watch)
    cands = {}
    for k in cand:
        f = R["factors"][k]
        grp, sign = f["group"], (-1 if f["group"] == "tc" else 1)
        sc = df[f"s_{grp}_{k}"].astype(float)
        a = sc.iloc[wk]
        st = E.score_stats(df, sc, sign)
        weeks = int(a.notna().sum())
        cands[k] = {
            "이름": f["name"], "그룹": "트렌드캐치(심리·과열, 맞는방향 −)" if grp == "tc" else "유동성(돈·경기, 맞는방향 +)",
            "자료": {"출처": f["source"], "변환": f.get("transform"), "비교일수": f.get("chg_days"), "방향": f["direction"],
                   "공개지연(일)": f["lag_days"], "주기": f.get("freq"), "받기": f.get("fetch")},
            "왜_후보인가": f.get("why"), "등록": {"날짜": f.get("added"), "누가": f.get("by")},
            "2023이후_점수있는_주": weeks, "넣을_수_있나": weeks >= C["min_weeks"] and (f.get("fetch") or {}).get("ok", f["source"]["type"] == "hist"),
            "지금_점수": r(sc.dropna().iloc[-1], 1) if sc.notna().any() else None,
            "2023이후(맞는방향_강도)": {kk: {"강도": st[kk]["맞는방향_강도"], "유의": st[kk]["유의"], "앞절반": adj(st[kk]["앞절반"], sign),
                                      "뒤절반": adj(st[kk]["뒤절반"], sign), "최근52주": adj(st[kk]["최근52주"], sign), "최근26주": adj(st[kk]["최근26주"], sign)}
                                  for kk in ("spx_20", "spx_60", "ndx_60", "kospi_20", "kospi_60")},
            "장기(2010~, 맞는방향_강도)": long_adj(FA.long_stats(k, f), sign),
            "같은주_주가와_동행(최근52주)": E.same_week(df, sc),
            "겹침": redundancy(df, sc, grp, cur),
            "넣으면_풍향계(단계 최대 가중치로)": effect(df, cur, grp, k, FL["add_" + grp]) if weeks >= 20 else "자료 부족",
        }
    # 사용 중인 지표
    act = {}
    for grp, sign in (("tc", -1), ("lq", 1)):
        cw = WM.norm(cur[grp])
        for k in WM.keys_of(cur, grp):
            sc = df[f"s_{grp}_{k}"].astype(float)
            st = E.score_stats(df, sc, sign)
            long = ((ana.get("items") or {}).get(f"{grp}_{k}") or {}).get("spx") or {}
            if k in R["factors"]:
                lg = long_adj(FA.long_stats(k, R["factors"][k]), sign)
            elif long:
                ic = long.get("ic") or {}
                lg = {"ic_4주(점수 방향 기준)": ic.get("4"), "ic_13주(점수 방향 기준)": ic.get("13"), "유의_13주": (long.get("sig") or {}).get("13"),
                      "앞뒤절반_같은방향": long.get("stable"), "메모": "analysis.json — 부호는 '점수가 높을수록 이후 수익률이 높았다'가 +. 트렌드캐치는 −가 맞는 방향"}
            else:
                lg = "장기 자료 없음"
            act[f"{grp}.{k}"] = {
                "이름": E.name_of(grp, k), "새_팩터": k in R["factors"], "지금_가중치%": round(cw[k], 2),
                "뺄_수_있나(가중치 기준)": cw[k] <= FL["remove_max_w"] + 1e-9,
                "2023이후(맞는방향_강도)": {kk: {"강도": st[kk]["맞는방향_강도"], "앞절반": adj(st[kk]["앞절반"], sign),
                                          "뒤절반": adj(st[kk]["뒤절반"], sign), "최근52주": adj(st[kk]["최근52주"], sign)} for kk in ("spx_20", "spx_60", "kospi_20")},
                "장기": lg,
                "점수있는_주%": r(sc.iloc[wk].notna().mean() * 100, 0),
                "겹침": redundancy(df, sc, grp, cur, skip=(grp, k)),
                "빼면_풍향계": effect(df, cur, grp, k, 0, remove=True),
            }
    out = {
        "_안내": "새 팩터 위원회 근거 자료. WEIGHTS.md 8절. '맞는방향_강도'는 클수록 그 점수가 이후 지수를 잘 맞혔다는 뜻(트렌드캐치는 부호를 뒤집어 계산).",
        "오늘": E.today_kst().isoformat(), "단계": level, "단계_이름": E.LEVEL_KO[level],
        "이번_한도": {"넣기_최대_개수": FL["add"], "넣는_가중치_최대(%)": {"tc": FL["add_tc"], "lq": FL["add_lq"]},
                   "빼기_최대_개수": FL["remove"], "뺄_수_있는_지표의_가중치_최대(%)": FL["remove_max_w"],
                   "후보_자격_최소_주": C["min_weeks"], "그룹별_최소_지표수": W["rules"].get("min_count"),
                   "새_팩터_최소_가중치(%)": W["rules"].get("new_min")},
        "합의_규칙": {"넣기·빼기": f"5명 중 {C['pass_add_remove']}명 이상 찬성", "후보 등록(관찰만, 점수에 안 들어감)": f"5명 중 {C['pass_register']}명 이상 찬성",
                  "넣는 가중치": "찬성한 위원들이 적은 가중치의 중앙값(한도 안)"},
        "후보_등록_방법": {"지원하는_자료": R["types"], "점수_방식": R["score_rule"],
                       "정의_예시": {k: R["factors"][k] for k in ("claims", "vixts")},
                       "메모": "일정한 주기로 나오는 어떤 값이든 후보가 될 수 있습니다. FRED에 있으면 바로 받을 수 있고(시리즈 ID가 정확해야 함), FRED에 없는 자료는 proposals에 action 'request'로 적어 주시면 선생님께 보고합니다."},
        "지금_가중치": {"버전": cur["v"], "트렌드캐치%": {k: round(v, 2) for k, v in WM.norm(cur["tc"]).items()},
                     "유동성%": {k: round(v, 2) for k, v in WM.norm(cur["lq"]).items()}, "심리비중": cur["wind"]["sent"]},
        "후보(관찰_중)": cands,
        "사용_중인_지표": act,
        "지난_위원회": (R.get("committee_log") or [])[-6:],
        "자료_요청_목록": R.get("requests", []),
        "팩터_도서관": library_section(),
    }
    if register_only:
        out["등록만"] = True
        out["임시_위원회_안내"] = ("선생님 지시로 여는 임시 위원회입니다. 이번에는 새 후보 관찰 등록(register)과 자료 요청(request)만 합니다. "
                              "넣기(add)·빼기(remove)는 정기 점검(주간·월간·분기)에서 단계 한도대로 하므로 이번에는 제안하지 마세요.")
    json.dump(out, open(BRIEF, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps({"brief": os.path.relpath(BRIEF, E.ROOT), "후보": len(cands), "사용_중": len(act),
                      "넣을_수_있는_후보": [k for k, v in cands.items() if v["넣을_수_있나"]]}, ensure_ascii=False))


def item_id(p):
    a = p.get("action")
    if a == "remove":
        return f"remove:{p.get('group')}.{p.get('key')}"
    return f"{a}:{p.get('key')}"


def cmd_items():
    items = {}
    for path in sorted(glob.glob(os.path.join(CDIR, "r1_*.json"))):
        m = json.load(open(path, encoding="utf-8"))
        for p in m.get("proposals", []):
            if p.get("action") not in ("add", "remove", "register", "request"):
                continue
            iid = item_id(p)
            it = items.setdefault(iid, {"안건": iid, "action": p["action"], "key": p.get("key"), "group": p.get("group"),
                                        "제안한_위원": [], "제안_가중치": [], "이유": [], "def": p.get("def")})
            it["제안한_위원"].append(m.get("member"))
            if p.get("weight") is not None:
                it["제안_가중치"].append(p["weight"])
            it["이유"].append(f"{m.get('member')}: {p.get('why', '')}")
            if p["action"] == "register" and p.get("def"):
                it.setdefault("정의_후보", {})[m.get("member")] = p["def"]
    # 같은 자료·같은 그룹을 다른 키로 등록하자는 안건은 서로 겹친다고 표시(둘 다 통과하면 찬성이 많은 쪽만 남김)
    sig = {}
    for iid, it in items.items():
        if it["action"] != "register":
            continue
        defs = list((it.get("정의_후보") or {}).values()) or [it.get("def") or {}]
        for d in defs:
            src = d.get("source") or {}
            k = (json.dumps(src, sort_keys=True, ensure_ascii=False), d.get("group"))
            sig.setdefault(k, set()).add(iid)
    for ids in sig.values():
        if len(ids) > 1:
            for iid in ids:
                items[iid]["겹치는_안건"] = sorted(ids - {iid})
    for it in items.values():
        dd = it.get("정의_후보") or {}
        uniq = {json.dumps(d, sort_keys=True, ensure_ascii=False) for d in dd.values()}
        if len(uniq) > 1:
            it["안내"] = "위원마다 정의가 다릅니다(정의_후보). 찬성할 때 \"def_from\": \"<위원 ID>\"로 어느 정의를 쓸지 고르세요. 찬성표에서 가장 많이 고른 정의로 등록합니다(같으면 먼저 제안한 위원 것)."
    out = {"안건": list(items.values()), "위원별_요약": {}}
    for path in sorted(glob.glob(os.path.join(CDIR, "r1_*.json"))):
        m = json.load(open(path, encoding="utf-8"))
        out["위원별_요약"][m.get("member")] = m.get("summary", "")
    json.dump(out, open(os.path.join(CDIR, "items.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps({"안건_수": len(items), "안건": list(items)}, ensure_ascii=False))


def cmd_tally():
    W = WM.load()
    cur = WM.current(W)
    R = FA.load()
    brief = json.load(open(BRIEF, encoding="utf-8"))
    level = brief["단계"]
    FL = W["rules"]["levels"][level]["factors"]
    C = W["rules"]["committee"]
    members = {m["id"]: m for m in C["members"]}
    items = json.load(open(os.path.join(CDIR, "items.json"), encoding="utf-8"))["안건"] if os.path.exists(os.path.join(CDIR, "items.json")) else []
    votes = {}
    for path in sorted(glob.glob(os.path.join(CDIR, "r2_*.json"))):
        m = json.load(open(path, encoding="utf-8"))
        if m.get("member") in members:
            votes[m["member"]] = m.get("votes", {})
    reg_only = bool(brief.get("등록만"))
    res = {"date": E.today_kst().isoformat(), "level": level, "등록만": reg_only, "members_voted": sorted(votes), "adds": [], "removes": [], "registers": [],
           "requests": [], "rejected": [], "tally": {}}
    passed = []
    for it in items:
        iid = it["안건"]
        yes = [mid for mid, v in votes.items() if (v.get(iid) or {}).get("vote") == "찬성"]
        no = [mid for mid, v in votes.items() if (v.get(iid) or {}).get("vote") == "반대"]
        res["tally"][iid] = {"찬성": yes, "반대": no, "기권·무응답": [m for m in members if m not in yes and m not in no]}
        need = C["pass_register"] if it["action"] in ("register", "request") else C["pass_add_remove"]
        if len(yes) < need:
            res["rejected"].append({"안건": iid, "이유": f"찬성 {len(yes)}명 < {need}명"})
            continue
        ws = [float(votes[mid][iid]["weight"]) for mid in yes if votes[mid][iid].get("weight") is not None]
        passed.append((it, yes, ws))
    passed.sort(key=lambda x: -len(x[1]))
    n_add = n_rem = 0
    keep = {"tc": len(WM.keys_of(cur, "tc")), "lq": len(WM.keys_of(cur, "lq"))}
    for it, yes, ws in passed:
        a, k = it["action"], it["key"]
        if reg_only and a in ("add", "remove"):
            res["rejected"].append({"안건": it["안건"], "이유": "임시 위원회(등록만) — 넣기·빼기는 정기 점검에서"})
            continue
        if a == "add":
            f = R["factors"].get(k)
            cb = (brief["후보(관찰_중)"].get(k) or {})
            if not f or f.get("status") != "watch" or not cb.get("넣을_수_있나"):
                res["rejected"].append({"안건": it["안건"], "이유": "관찰 중인 후보가 아니거나 자료가 부족(자격 미달)"})
                continue
            if n_add >= FL["add"]:
                res["rejected"].append({"안건": it["안건"], "이유": f"이번 단계 넣기 최대 {FL['add']}개 초과"})
                continue
            cap = FL["add_" + f["group"]]
            w = min(round(statistics.median(ws) * 20) / 20 if ws else cap, cap)
            w = max(w, W["rules"].get("new_min", 0.5))
            res["adds"].append({"key": k, "group": f["group"], "weight": w, "votes": len(yes), "name": f["name"]})
            n_add += 1
        elif a == "remove":
            g = it.get("group")
            if g not in ("tc", "lq") or k not in cur[g]:
                res["rejected"].append({"안건": it["안건"], "이유": "지금 쓰는 지표가 아님"})
                continue
            w = WM.norm(cur[g])[k]
            if w > FL["remove_max_w"] + 1e-9:
                res["rejected"].append({"안건": it["안건"], "이유": f"가중치 {w:.2f}% > 이번 단계에서 뺄 수 있는 최대 {FL['remove_max_w']}% (먼저 가중치를 줄여야 함)"})
                continue
            if n_rem >= FL["remove"] or keep[g] - 1 < (W["rules"].get("min_count") or {}).get(g, 0):
                res["rejected"].append({"안건": it["안건"], "이유": "빼기 개수 한도 또는 그룹 최소 지표 수"})
                continue
            res["removes"].append({"key": k, "group": g, "weight": round(w, 2), "votes": len(yes), "name": E.name_of(g, k)})
            keep[g] -= 1
            n_rem += 1
        elif a == "register":
            dd = it.get("정의_후보") or {}
            pick = [votes[mid][it["안건"]].get("def_from") for mid in yes if votes[mid][it["안건"]].get("def_from") in dd]
            order = [x for x in it["제안한_위원"] if x in dd]
            if pick:
                best = max(order, key=lambda x: (pick.count(x), -order.index(x)))
            else:
                best = order[0] if order else None
            d = dd.get(best) if best else (it.get("def") or {})
            dup = [r for r in res["registers"] if r["안건"] in (it.get("겹치는_안건") or [])]
            if dup:
                res["rejected"].append({"안건": it["안건"], "이유": f"같은 자료를 다른 키로 등록하는 안건({dup[0]['안건']})이 먼저 통과(찬성 {dup[0]['votes']}명, 같으면 먼저 제안된 안건)"})
                continue
            errs = FA.validate(k, d, R) + ([f"이미 있는 키 {k}"] if k in R["factors"] else [])
            if errs:
                res["rejected"].append({"안건": it["안건"], "이유": "; ".join(errs)})
                continue
            res["registers"].append({"key": k, "def": d, "votes": len(yes), "def_from": best, "안건": it["안건"]})
        elif a == "request":
            res["requests"].append({"key": k, "why": it["이유"], "votes": len(yes)})
    s = []
    if res["adds"]:
        s.append("넣기: " + ", ".join(f"{x['name']}({x['weight']}%)" for x in res["adds"]))
    if res["removes"]:
        s.append("빼기: " + ", ".join(x["name"] for x in res["removes"]))
    if res["registers"]:
        s.append("새 후보 관찰: " + ", ".join(x["def"].get("name", x["key"]) for x in res["registers"]))
    s.append(f"합의 안 된 안건 {len(res['rejected'])}개")
    res["summary"] = " · ".join(s)
    if res["requests"]:
        have = {(x.get("date"), x.get("key")) for x in R.setdefault("requests", [])}
        R["requests"].extend({"date": res["date"], **q} for q in res["requests"] if (res["date"], q["key"]) not in have)
        FA.save(R)
    json.dump(res, open(RESULT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps({k: res[k] for k in ("level", "members_voted", "adds", "removes", "summary")} | {"registers": [x["key"] for x in res["registers"]]}, ensure_ascii=False, indent=1))


def cmd_apply_register():
    """임시 위원회(등록만) 결과 반영 — 새 후보 watch 등록과 위원회 기록만. 가중치 버전·점검 기록(reviews)은 건드리지 않는다."""
    if not os.path.exists(RESULT):
        sys.exit("위원회 결과(data/raw/committee_result.json)가 없습니다.")
    com = json.load(open(RESULT, encoding="utf-8"))
    today = E.today_kst().isoformat()
    if com.get("date") != today or not com.get("등록만"):
        sys.exit("오늘 임시 위원회(등록만) 결과가 아닙니다.")
    W = WM.load()
    cur = WM.current(W)
    R = FA.load()
    for g in com.get("registers", []):
        d = dict(g["def"])
        d.update({"status": "watch", "added": today, "by": "위원회 합의(임시 위원회)"})
        R["factors"][g["key"]] = d
    R.setdefault("committee_log", []).append({"date": today, "level": "임시(등록만)", "version": cur["v"], "adds": [], "removes": [],
                                              "registers": [g["key"] for g in com.get("registers", [])],
                                              "rejected": com.get("rejected", [])[:20], "summary": com.get("summary", "")})
    FA.save(R)
    LAB.sync_status()
    print(json.dumps({"등록": [g["key"] for g in com.get("registers", [])], "요약": com.get("summary")}, ensure_ascii=False))


if __name__ == "__main__":
    a = [x for x in sys.argv[1:] if not x.startswith("--")]
    if not a or a[0] not in ("brief", "items", "tally", "apply-register"):
        sys.exit(__doc__)
    {"brief": lambda: cmd_brief(a[1] if len(a) > 1 else (E.level_of(E.today_kst()) or "weekly"), "--register-only" in sys.argv),
     "items": cmd_items, "tally": cmd_tally, "apply-register": cmd_apply_register}[a[0]]()
