"""GitHub 작업(Actions)에서 열쇠(비밀값)가 필요한 일만 한다. 열쇠는 GitHub 비밀값 FINVIZ_AUTH·FRED_KEY·ONESIGNAL_KEY.
  python scripts/actions_run.py collect [--no-board|--force-board]  → collect.py (+ 전체 수집이면 analyze.py), 결과 data/runs/collect_last.json
  python scripts/actions_run.py notify                              → data/notify/latest.json 내용으로 OneSignal 알림, 결과 data/notify/result.json
  python scripts/actions_run.py check                               → 열쇠 3개가 맞는지만 확인(알림은 보내지 않음), 결과 data/runs/keys_check.json
  python scripts/actions_run.py factors                             → 새 팩터 원자료(FRED)와 장기 지수 받기, 결과 data/runs/factors_last.json
결과 파일·로그에는 열쇠를 절대 남기지 않는다(공개 저장소)."""
import datetime as dt, json, os, re, subprocess, sys, urllib.request, urllib.error

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
KEYS = [os.environ.get(k, '').strip() for k in ('FINVIZ_AUTH', 'FRED_KEY', 'ONESIGNAL_KEY')]
APP_ID = 'c323691f-5bf6-4942-aac1-fd6254f1b0c0'
KST = dt.timezone(dt.timedelta(hours=9))


def scrub(s):
    s = str(s)
    for k in KEYS:
        if k:
            s = s.replace(k, '***')
    return re.sub(r"(auth|api_key)=[^&'\" ]+", r"\1=***", s)


def save(rel, obj):
    p = os.path.join(ROOT, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)


def now():
    return dt.datetime.now(KST).strftime('%Y-%m-%d %H:%M:%S KST')


def run(args):
    r = subprocess.run([sys.executable] + args, cwd=ROOT, capture_output=True, text=True)
    out = scrub(r.stdout + ('\n' + r.stderr if r.stderr else ''))
    print(out)
    return r.returncode, out


def last_json(text):
    for line in reversed(text.strip().splitlines()):
        line = line.strip()
        if line.startswith('{') and line.endswith('}'):
            try:
                return json.loads(line)
            except ValueError:
                pass
    return None


def collect(extra):
    started = now()
    # 새 팩터(watch·active) 원자료를 먼저 새로 받는다 — 실패해도 수집은 계속
    rcf, outf = run(['scripts/factors.py', 'fetch', '--no-long'])
    rc, out = run(['scripts/collect.py'] + extra)
    res = {'started': started, 'args': extra, 'collect_rc': rc, 'result': last_json(out), 'factors': last_json(outf),
           'log_tail': out.strip().splitlines()[-25:]}
    if rc == 0 and '--no-board' not in extra:
        rc2, out2 = run(['scripts/analyze.py'])
        res.update({'analyze_rc': rc2, 'analyze_tail': out2.strip().splitlines()[-8:]})
    res['finished'] = now()
    save('data/runs/collect_last.json', res)
    return rc


def onesignal(body):
    req = urllib.request.Request('https://api.onesignal.com/notifications?c=push', data=json.dumps(body).encode(),
                                 headers={'Authorization': f'Key {KEYS[2]}', 'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read() or b'{}')
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read() or b'{}')
        except ValueError:
            return e.code, {}


def notify():
    msg = json.load(open(os.path.join(ROOT, 'data', 'notify', 'latest.json'), encoding='utf-8'))
    body = {'app_id': APP_ID, 'target_channel': 'push', 'included_segments': ['Total Subscriptions'],
            'headings': {'en': msg['heading'], 'ko': msg['heading']}, 'contents': {'en': msg['contents'], 'ko': msg['contents']},
            'url': msg.get('url') or 'https://hangseokemail-spec.github.io/seoks/'}
    code, resp = onesignal(body)
    save('data/notify/result.json', {'sent': now(), 'for': msg.get('date'), 'status': code,
                                      'id': resp.get('id'), 'errors': scrub(resp.get('errors')) if resp.get('errors') else None})
    print('알림', code, scrub(resp.get('errors') or 'ok'))
    return 0


def get(url):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'}), timeout=30) as r:
            return r.status, r.read(400).decode('utf-8', 'replace')
    except urllib.error.HTTPError as e:
        return e.code, ''
    except Exception as e:
        return 0, scrub(e)[:120]


def factors(extra):
    """새 팩터 후보·사용 중 팩터의 원자료(FRED)와 장기 지수를 받는다."""
    started = now()
    rc, out = run(['scripts/factors.py', 'fetch'] + [x for x in extra if not x.startswith('--')])
    save('data/runs/factors_last.json', {'started': started, 'rc': rc, 'result': last_json(out), 'log_tail': out.strip().splitlines()[-15:], 'finished': now()})
    return rc


def check():
    res = {'checked': now()}
    s, body = get(f'https://elite.finviz.com/quote_export.ashx?t=SPY&p=d&auth={KEYS[0]}')   # collect.py와 같은 주소
    res['FINVIZ_AUTH'] = 'ok' if s == 200 and ('Date' in body or 'Close' in body) else f'실패 {s}' if KEYS[0] else '없음'
    s, body = get(f'https://api.stlouisfed.org/fred/series/observations?series_id=DGS10&file_type=json&limit=1&api_key={KEYS[1]}')
    res['FRED_KEY'] = 'ok' if s == 200 and 'observations' in body else f'실패 {s}' if KEYS[1] else '없음'
    if KEYS[2]:   # 아무에게도 가지 않는 대상(없는 사용자)으로 보내 열쇠만 확인한다
        code, resp = onesignal({'app_id': APP_ID, 'target_channel': 'push', 'include_aliases': {'external_id': ['seoks-key-check-nobody']},
                                'contents': {'en': 'key check'}})
        res['ONESIGNAL_KEY'] = ('실패(열쇠 거부)' if code in (401, 403) else 'ok') + f' ({code})'
        res['onesignal_reply'] = scrub(resp.get('errors') or resp)[:300]
        res['onesignal_key_shape'] = {'length': len(KEYS[2]), 'starts_os_v2': KEYS[2].startswith('os_v2_'),
                                      'has_space_or_newline': any(c.isspace() for c in KEYS[2])}
    else:
        res['ONESIGNAL_KEY'] = '없음'
    save('data/runs/keys_check.json', res)
    print(json.dumps(res, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    what = sys.argv[1] if len(sys.argv) > 1 else 'collect'
    sys.exit({'collect': lambda: collect(sys.argv[2:]), 'notify': notify, 'check': check, 'factors': lambda: factors(sys.argv[2:])}[what]())
