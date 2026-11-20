#!/usr/bin/env python3
"""오늘 아침 작업의 미국 날짜·휴장 여부와, 웹 지표(data/manual.json) 중 오늘 들어가 있어야 할 값을 알려 준다.

    python3 scripts/usday.py            # 오늘(한국 시각) 기준
    python3 scripts/usday.py 2026-11-21 # 한국 날짜를 정해서

출력(JSON):
  us_date   이번 작업이 다룰 미국 날짜(한국 날짜 - 1일; 아침 06시대 작업은 미국 정규장 마감 직후)
  trading   그 날짜가 미국 증시(NYSE) 거래일인지. false면 "오늘은 미국 휴장"으로 끝낸다.
  due       지표별로 오늘 있어야 하는 가장 늦은 기준일
            fg     = us_date (CNN 공포탐욕, 매일. 장중 값도 기준일이 맞으면 인정)
            pc     = us_date 바로 전 거래일 (Cboe 풋콜은 미 동부 20시경 공개라 아침 작업 때는 하루 늦음)
            aaii   = us_date 이전 가장 가까운 목요일 (그 목요일이 휴장이면 이틀 앞까지 인정)
            margin = 미국 날짜가 25일 이후면 전달, 아니면 전전달 (FINRA는 다음 달 셋째 주쯤 공개)
  have      manual.json의 지표별 마지막 기준일
  missing   due보다 오래된 지표 목록 → DAILY.md 3단계대로 찾고, 끝내 못 찾으면 선생님께 알리고 발간을 멈춘다.
"""
import datetime as dt
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

try:
    import holidays  # pip install holidays --break-system-packages
    _NYSE = holidays.NYSE(years=range(2020, 2035))
except Exception:  # 패키지가 없으면 주말만 거른다(보고에 표시)
    _NYSE = None


def is_trading(d):
    if d.weekday() >= 5:
        return False
    return not (_NYSE is not None and d in _NYSE)


def prev_trading(d):
    d -= dt.timedelta(days=1)
    while not is_trading(d):
        d -= dt.timedelta(days=1)
    return d


def today_kst():
    return (dt.datetime.utcnow() + dt.timedelta(hours=9)).date()


def main():
    kst = dt.date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else today_kst()
    us = kst - dt.timedelta(days=1)
    out = {"kst": kst.isoformat(), "us_date": us.isoformat(), "trading": is_trading(us),
           "holiday_list": "NYSE(holidays 패키지)" if _NYSE is not None else "없음 — 주말만 확인(pip install holidays)"}
    if not out["trading"]:
        out["reason"] = "주말" if us.weekday() >= 5 else f"미국 휴장({_NYSE.get(us)})"
        print(json.dumps(out, ensure_ascii=False, indent=1))
        return
    thu = us - dt.timedelta(days=(us.weekday() - 3) % 7)
    aaii_min = thu - dt.timedelta(days=2) if not is_trading(thu) else thu
    first = us.replace(day=1)
    m1 = (first - dt.timedelta(days=1)).replace(day=1)          # 전달
    m2 = (m1 - dt.timedelta(days=1)).replace(day=1)             # 전전달
    margin_due = (m1 if us.day >= 25 else m2).strftime("%Y-%m")
    due = {"fg": us.isoformat(), "pc": prev_trading(us).isoformat(), "aaii": aaii_min.isoformat(), "margin": margin_due}
    man = json.load(open(os.path.join(ROOT, "data", "manual.json"), encoding="utf-8"))

    def last(k, f):
        xs = [x.get(f) for x in man.get(k, []) if x.get(f)]
        return max(xs) if xs else None

    have = {"fg": last("fg", "date"), "pc": last("pc", "date"), "aaii": last("aaii", "date"), "margin": last("margin", "month")}
    missing = [k for k in due if not have[k] or have[k] < due[k]]
    names = {"fg": "CNN 공포탐욕", "pc": "Cboe 풋콜 비율", "aaii": "AAII 개인투자자 심리", "margin": "FINRA 신용융자"}
    out.update({"due": due, "have": have, "missing": missing,
                "missing_names": [f"{names[k]}({due[k]})" for k in missing]})
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
