"""새 팩터(신호) 등록부와 계산 — data/factors.json

원래 지표 20개(트렌드캐치 9 · 유동성 11)는 collect.py가 고정 기준으로 점수를 매긴다.
여기서는 그 밖의 '일정한 주기로 나오는 어떤 값'이든 팩터 후보로 등록해 같은 1~5점으로 바꾼다.
  - 상태: watch(관찰만, 점수에 안 들어감) → active(가중치를 받아 점수에 들어감) → removed(뺌)
  - 넣기·빼기·후보 등록은 위원회(Fable 2 · Opus 3)가 합의한 것만 (scripts/committee.py, WEIGHTS.md 8절)
  - 점수: 공개 지연(lag)을 반영해 그날 알 수 있던 값만 쓰고, 최근 3년 값 중 지금 값의 위치를 5등분해 1~5점.
    방향 +1 = 값이 클수록 점수가 높다(트렌드캐치에서는 과열 쪽, 유동성에서는 좋은 쪽), −1 = 반대.

python3 scripts/factors.py status            → 등록된 팩터와 자료 상태
python3 scripts/factors.py fetch [키 ...]     → (GitHub 작업에서만, FRED_KEY 필요) 원자료와 장기 지수 받기
python3 scripts/factors.py show <키>          → 최근 값·점수
"""
import datetime as dt
import json
import os
import re
import sys
import urllib.request

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
REG = os.path.join(DATA, "factors.json")
RAWDIR = os.path.join(DATA, "factors")
LONG = os.path.join(DATA, "hist", "index_long.json")
KST = dt.timezone(dt.timedelta(hours=9))
FETCH_START = "2000-01-01"
BUILTIN_TC = ["fg", "aaii", "vix", "hy", "pc", "margin", "a200", "rsi", "dev"]
BUILTIN_LQ = ["fed", "nl", "m2", "effr", "hy", "dxy", "margin", "bank", "vol", "nfci", "y10"]
TYPES = ("fred", "fred_ratio", "hist")
TRANSFORMS = ("level", "chg", "pct")


def load():
    with open(REG, encoding="utf-8") as f:
        return json.load(f)


def save(R):
    with open(REG, "w", encoding="utf-8") as f:
        json.dump(R, f, ensure_ascii=False, indent=1)


def keys(R=None, status=("active",), group=None):
    R = R or load()
    return [k for k, f in R["factors"].items() if f.get("status") in status and (group is None or f["group"] == group)]


def validate(key, f, R=None):
    """등록 정의 검사. 반환: 오류 목록."""
    R = R or load()
    e = []
    if not re.fullmatch(r"[a-z][a-z0-9_]{1,15}", key or ""):
        e.append(f"키 '{key}': 영문 소문자로 시작하는 2~16자(소문자·숫자·_)")
    if key in BUILTIN_TC or key in BUILTIN_LQ:
        e.append(f"키 '{key}': 원래 지표와 같은 이름")
    if f.get("group") not in ("tc", "lq"):
        e.append("group은 tc(심리·과열) 또는 lq(돈·경기)")
    src = f.get("source") or {}
    if src.get("type") not in TYPES:
        e.append(f"source.type은 {TYPES} 중 하나 (그 밖의 자료는 requests에 적기)")
    if src.get("type") == "fred" and not src.get("id"):
        e.append("fred: source.id(FRED 시리즈 ID) 필요")
    if src.get("type") == "fred_ratio" and not (src.get("num") and src.get("den")):
        e.append("fred_ratio: source.num, source.den 필요")
    if src.get("type") == "hist" and not os.path.exists(os.path.join(DATA, "hist", str(src.get("file")))):
        e.append(f"hist: data/hist/{src.get('file')} 없음")
    if f.get("transform", "level") not in TRANSFORMS:
        e.append(f"transform은 {TRANSFORMS}")
    if f.get("transform") in ("chg", "pct") and not int(f.get("chg_days") or 0) > 0:
        e.append("chg/pct는 chg_days(며칠 전과 비교) 필요")
    if f.get("direction") not in (1, -1):
        e.append("direction은 1 또는 -1")
    for k in ("lag_days", "stale_days"):
        if not isinstance(f.get(k), (int, float)) or f[k] < 0:
            e.append(f"{k}(0 이상 숫자) 필요")
    for k in ("name", "why"):
        if not (f.get(k) or "").strip():
            e.append(f"{k} 필요")
    return e


# ---------------------------------------------------------------- 원자료 받기 (GitHub 작업)
def _http(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def _fred(sid):
    key = os.environ.get("FRED_KEY", "").strip()
    if not key:
        raise RuntimeError("FRED_KEY 없음")
    d = json.loads(_http(f"https://api.stlouisfed.org/fred/series/observations?series_id={sid}"
                         f"&api_key={key}&file_type=json&observation_start={FETCH_START}"))
    return {o["date"]: float(o["value"]) for o in d["observations"] if o["value"] not in (".", "")}


def _naver_long(code):
    end = (dt.date.today() + dt.timedelta(days=1)).strftime("%Y%m%d")
    d = json.loads(_http(f"https://api.stock.naver.com/chart/foreign/index/{code}/day?startDateTime=199901010000&endDateTime={end}0000"))
    return pd.Series({pd.Timestamp(x["localDate"]): float(x["closePrice"]) for x in d}).sort_index()


def fetch(only=None, with_long=True):
    """등록된 watch·active 팩터의 원자료를 받아 data/factors/<키>.json 에 저장. 실패는 등록부에 기록."""
    R = load()
    os.makedirs(RAWDIR, exist_ok=True)
    now = dt.datetime.now(KST).strftime("%Y-%m-%d %H:%M KST")
    done = {}
    for k, f in R["factors"].items():
        if f.get("status") not in ("watch", "active") or (only and k not in only):
            continue
        src = f["source"]
        try:
            if src["type"] == "fred":
                series = {src["id"]: _fred(src["id"])}
            elif src["type"] == "fred_ratio":
                series = {src["num"]: _fred(src["num"]), src["den"]: _fred(src["den"])}
            else:
                series = {}
            if series:
                with open(os.path.join(RAWDIR, f"{k}.json"), "w", encoding="utf-8") as fp:
                    json.dump({"fetched": now, "series": series}, fp, ensure_ascii=False, separators=(",", ":"))
            s = raw_series(k, f)
            f["fetch"] = {"at": now, "ok": True, "n": int(s.notna().sum()), "first": f"{s.index[0]:%Y-%m-%d}" if len(s) else None,
                          "last_obs": f"{s.index[-1]:%Y-%m-%d}" if len(s) else None}
            done[k] = "ok"
        except Exception as ex:  # noqa: BLE001
            f["fetch"] = {"at": now, "ok": False, "err": str(ex)[:160].replace(os.environ.get("FRED_KEY", "~~~") or "~~~", "***")}
            done[k] = "실패"
    save(R)
    if with_long:
        try:
            spx = _naver_long(".INX")
            ndx = pd.Series({pd.Timestamp(d): v for d, v in _fred("NASDAQ100").items()}).sort_index()
            wk = lambda s: {f"{d:%Y-%m-%d}": round(float(v), 2) for d, v in s.resample("W-FRI").last().dropna().items()}
            with open(LONG, "w", encoding="utf-8") as fp:
                json.dump({"fetched": now, "note": "주간(금요일) 종가. S&P500 = 네이버 .INX, 나스닥100 = FRED NASDAQ100", "spx": wk(spx), "ndx": wk(ndx)},
                          fp, ensure_ascii=False, separators=(",", ":"))
            done["_index_long"] = "ok"
        except Exception as ex:  # noqa: BLE001
            done["_index_long"] = f"실패 {str(ex)[:80]}"
    return done


# ---------------------------------------------------------------- 계산 (열쇠 없이)
def raw_series(key, f=None):
    """관측일 기준 원자료(Series)."""
    f = f or load()["factors"][key]
    src = f["source"]
    if src["type"] == "hist":
        with open(os.path.join(DATA, "hist", src["file"]), encoding="utf-8") as fp:
            d = json.load(fp)
        d = d.get("data", d) if isinstance(d, dict) else d
        return pd.Series({pd.Timestamp(k): float(v) for k, v in d.items() if v is not None}).sort_index()
    p = os.path.join(RAWDIR, f"{key}.json")
    if not os.path.exists(p):
        return pd.Series(dtype=float)
    with open(p, encoding="utf-8") as fp:
        S = json.load(fp)["series"]
    ser = {sid: pd.Series({pd.Timestamp(k): v for k, v in obs.items()}).sort_index() for sid, obs in S.items()}
    if src["type"] == "fred":
        return ser.get(src["id"], pd.Series(dtype=float)).astype(float)
    a, b = ser.get(src["num"]), ser.get(src["den"])
    if a is None or b is None:
        return pd.Series(dtype=float)
    j = pd.concat([a, b], axis=1, join="inner").dropna()
    return (j.iloc[:, 0] / j.iloc[:, 1]).astype(float)


def transformed(f, s):
    """관측일 기준 변환값: level(그대로) · chg(chg_days일 전과의 차이) · pct(chg_days일 전 대비 %)."""
    s = s.dropna()
    t = f.get("transform", "level")
    if t == "level" or s.empty:
        return s
    n = int(f["chg_days"])
    past = s.reindex(s.index - pd.Timedelta(days=n), method="ffill")
    past.index = s.index
    old_enough = s.index - pd.Timedelta(days=n) >= s.index[0]
    out = (s - past) if t == "chg" else (s / past - 1) * 100
    return out.where(old_enough).dropna()


def scored(f, tr, window_days=1095, min_n=20):
    """관측일마다: 최근 window_days일 값들 중 지금 값의 위치(0~1) → 5등분 1~5점. 방향 −1이면 뒤집는다."""
    tr = tr.dropna()
    if tr.empty:
        return tr
    idx, v = tr.index.values, tr.values
    start = idx[0] + np.timedelta64(int(window_days * 0.66), "D")   # 최소 2년치는 있어야
    lo = np.searchsorted(idx, idx - np.timedelta64(window_days, "D"), side="left")
    out = np.full(len(v), np.nan)
    for i in range(len(v)):
        if idx[i] < start:
            continue
        w = v[lo[i]:i + 1]
        if len(w) < min_n:
            continue
        pct = (np.sum(w < v[i]) + 0.5 * (np.sum(w == v[i]) - 1)) / (len(w) - 1)
        sc = 1 + min(int(pct * 5), 4)
        out[i] = sc if f.get("direction", 1) == 1 else 6 - sc
    return pd.Series(out, index=tr.index).dropna()


def at_dates(s, dates, lag, stale):
    """dates 각 날짜에 공개되어 있던 최신 관측값(관측일 + lag일에 공개)."""
    s = s.dropna()
    dates = pd.DatetimeIndex(dates)
    if s.empty:
        return pd.Series(np.nan, index=dates), pd.Series(pd.NaT, index=dates)
    avail = pd.DataFrame({"avail": s.index + pd.Timedelta(days=lag), "obs": s.index, "v": s.values}).sort_values("avail")
    left = pd.DataFrame({"d": dates}).sort_values("d")
    m = pd.merge_asof(left, avail, left_on="d", right_on="avail", direction="backward").set_index("d")
    m.loc[(m.index - m["obs"]).dt.days > stale, "v"] = np.nan
    return m["v"].reindex(dates), m["obs"].reindex(dates)


def series_for(key, dates, f=None):
    """날짜별 (변환값, 점수, 관측일)."""
    f = f or load()["factors"][key]
    tr = transformed(f, raw_series(key, f))
    sc = scored(f, tr)
    val, obs = at_dates(tr, dates, f["lag_days"], f["stale_days"])
    s, _ = at_dates(sc, dates, f["lag_days"], f["stale_days"])
    return val, s, obs


def frame(dates, which=None, R=None):
    """DataFrame: <grp>_<키> 변환값, s_<grp>_<키> 점수 (which: 키 목록, 기본은 active)."""
    R = R or load()
    which = which if which is not None else keys(R)
    cols = {}
    for k in which:
        f = R["factors"][k]
        v, s, _ = series_for(k, dates, f)
        cols[f"{f['group']}_{k}"] = v
        cols[f"s_{f['group']}_{k}"] = s
    return pd.DataFrame(cols, index=pd.DatetimeIndex(dates))


def long_index():
    if not os.path.exists(LONG):
        return None
    with open(LONG, encoding="utf-8") as fp:
        d = json.load(fp)
    return {k: pd.Series({pd.Timestamp(a): b for a, b in d[k].items()}).sort_index() for k in ("spx", "ndx") if k in d}


def long_stats(key, f=None, start="2010-07-09"):
    """2010년부터 주간: 점수와 4·13주 뒤 S&P500·나스닥100 수익률의 순위상관(원래 부호) + 앞·뒤 절반."""
    f = f or load()["factors"][key]
    L = long_index()
    if not L:
        return "장기 지수 자료 없음(GitHub 작업 factors 실행 필요)"
    spx = L["spx"].loc[start:]
    d = spx.index
    _, s, _ = series_for(key, d, f)
    out = {"표본(주)": int(s.notna().sum()), "시작": f"{s.dropna().index[0]:%Y-%m-%d}" if s.notna().any() else None}
    for nm, px in L.items():
        px = px.reindex(d)
        for h in (4, 13):
            r = px.shift(-h) / px - 1
            m = s.notna() & r.notna()
            if m.sum() < 52 or s[m].nunique() < 2:
                out[f"{nm}_{h}주"] = None
                continue
            ic = float(s[m].corr(r[m], method="spearman"))
            idx = s[m].index
            half = len(idx) // 2
            h1 = float(s[idx[:half]].corr(r[idx[:half]], method="spearman"))
            h2 = float(s[idx[half:]].corr(r[idx[half:]], method="spearman"))
            n = int(m.sum())
            out[f"{nm}_{h}주"] = {"ic": round(ic, 3), "앞절반": round(h1, 3), "뒤절반": round(h2, 3), "n주": n,
                                  "유의": bool(abs(ic) > 2 / np.sqrt(max(n / h, 1)))}
    return out


def meta(key, f=None):
    """사이트·자료 묶음용 설명."""
    f = f or load()["factors"][key]
    src = f["source"]
    url = (f"https://fred.stlouisfed.org/series/{src['id']}" if src["type"] == "fred" else
           f"https://fred.stlouisfed.org/series/{src['num']}" if src["type"] == "fred_ratio" else None)
    tr = {"level": "값 그대로", "chg": f"{f.get('chg_days')}일 전과의 차이", "pct": f"{f.get('chg_days')}일 전 대비 변화율(%)"}[f.get("transform", "level")]
    up = "높을수록 점수가 높습니다" if f["direction"] == 1 else "낮을수록 점수가 높습니다"
    return {"key": key, "name": f["name"], "short": f.get("short") or f["name"][:6], "unit": f.get("unit", ""), "dec": f.get("dec", 2),
            "cat": f.get("cat"), "desc": f.get("desc") or f["why"], "freq": f.get("freq", ""), "new": True,
            "formula": f"{tr}을 씁니다. 그날까지 공개된 최근 3년 값 중 지금 값이 어디쯤인지를 5등분해 1~5점을 매깁니다({up}).",
            "bins": [["최근 3년 중 상위 20%", 5 if f["direction"] == 1 else 1], ["상위 20~40%", 4 if f["direction"] == 1 else 2],
                     ["중간 20%", 3], ["하위 20~40%", 2 if f["direction"] == 1 else 4], ["하위 20%", 1 if f["direction"] == 1 else 5]],
            "src": {"name": f.get("src_name") or (f"FRED {src.get('id') or src.get('num') + '/' + src.get('den')}" if src["type"] != "hist" else "자체 계산"), "url": url},
            "added": f.get("activated") or f.get("added"), "why": f["why"]}


def cmd_status():
    R = load()
    rows = []
    for k, f in R["factors"].items():
        s = raw_series(k, f)
        rows.append({"키": k, "이름": f["name"], "그룹": f["group"], "상태": f["status"],
                     "자료": f"{s.index[0]:%Y-%m} ~ {s.index[-1]:%Y-%m-%d} ({len(s)})" if len(s) else "없음",
                     "받기": (f.get("fetch") or {}).get("ok")})
    print(json.dumps(rows, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a or a[0] not in ("status", "fetch", "show"):
        sys.exit(__doc__)
    if a[0] == "status":
        cmd_status()
    elif a[0] == "fetch":
        ks = [x for x in a[1:] if not x.startswith("--")]
        print(json.dumps(fetch(ks or None, with_long="--no-long" not in a), ensure_ascii=False))
    else:
        js = json.load(open(os.path.join(DATA, "series.json"), encoding="utf-8"))
        d = pd.DatetimeIndex(js["dates"])
        v, s, o = series_for(a[1], d)
        print(pd.DataFrame({"값": v, "점수": s, "관측일": o}).tail(15).to_string())
