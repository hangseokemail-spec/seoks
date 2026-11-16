# Seoks 매일 아침 작업 절차 (Claude 예약 작업용)

한국 시각 **화~토 06:04**에 실행한다(미국 월~금 정규장 마감분, 서머타임과 관계없이 같은 시각). 컴퓨터는 필요 없다(클라우드 실행).
목표: **한국 시각 06:20 전후에 사이트·알림 발행**. 빠르게, 그러나 숫자는 정확하게.
API 키(FINVIZ_AUTH, FRED_KEY, ONESIGNAL_KEY)는 **GitHub 비밀값**에만 있다. 예약 작업 세션은 키를 갖지 않는다. 키가 필요한 일(수집·알림)은 `.github/triggers/<일>` 파일을 푸시해 **GitHub 작업(keys-work)**에 맡긴다. 키를 파일·커밋·메시지에 절대 쓰지 않는다.

**GitHub 작업 맡기는 법** (세 곳에서 쓴다):
```
cd /home/claude/seoks && git pull -q --rebase
echo "<인자> $(date -u +%FT%TZ)" > .github/triggers/<일>      # 일 = collect | notify | check
git add -A && git commit -qm "<일>" && git -c push.negotiate=true push -q
# 30초마다 상태 확인(최대 6분): gh run list -R hangseokemail-spec/seoks -L 1 --json status,conclusion
# completed가 되면 git pull -q --rebase 로 결과를 받는다
```

## 0. 역할 분담 — 해석·편집은 Fable, 실질적인 일은 Opus 5.5

| 단계 | 담당 | 내용 |
|---|---|---|
| 1~5 | **Opus 5.5** (메인 세션) | 준비 · 수집 · 웹 지표 보충 · 웹 사실 조사 · 자료 묶음 |
| 6 | **Fable** (하위 에이전트, `model: "fable"`) | 해석(코멘트 작성) · 편집(다듬기·자체 검사) · 회사 한 줄 설명 — 지침 `FABLE.md` |
| 7~10 | **Opus 5.5** (메인 세션) | 검사 · 저장 · 다른 사람 알림 · 마지막 메시지 |

- **가중치**(트렌드캐치·유동성 지표 비중, 풍향계 심리·유동성 비중)는 `data/weights.json`이 정하고, 매주 토요일 별도 예약 작업(주간·월간·분기 점검)에서 **가장 최신 Claude 모델(지금 Fable 5.2)만** 결정하고 Opus가 적용다(`WEIGHTS.md`). 매일 작업에서는 가중치를 건드리지 않는다. 풍향계 식은 brief의 `rules.풍향계_식`을 따른다.
- 메인 세션이 Opus 5.5(`claude-opus-5-5`)가 아니면: 2~5단계를 `Agent(model: "opus")` 하나에, 7~9단계를 또 다른 `Agent(model: "opus")` 하나에 맡기고 메인 세션은 순서만 진행한다.
- Opus는 코멘트 **문장 내용**을 쓰거나 고치지 않는다 (7단계의 예외만). 사실(숫자·뉴스·실적)은 Opus가 모으고, 그 사실로 무엇을 말할지는 Fable이 정한다.

## 1. 준비 (1분) — Opus
1. 저장소 연결: `hangseokemail-spec/seoks` (push 권한). `git clone --depth 1 https://github.com/hangseokemail-spec/seoks /home/claude/seoks`
2. `pip install pandas numpy --break-system-packages -q` (없을 때만)

## 2. 수집 (2~3분) — Opus가 GitHub 작업에 맡김
- 위 '맡기는 법'대로 `echo "run $(date -u +%FT%TZ)" > .github/triggers/collect` 를 푸시한다. GitHub 작업이 비밀값으로 `scripts/collect.py`와 이어서 `scripts/analyze.py`(지표 예측력 분석)를 돌리고 `data/`를 커밋한다.
- 끝나면 `git pull` 후 `data/runs/collect_last.json`을 본다: `result.date`가 오늘 미국 날짜이고 `result.board: true`면 정상. `log_tail`에 진행 기록이 있다.
- `finviz 날짜와 지수 날짜가 달라 현황판 생략`이면 5분 기다렸다 `echo "--force-board $(date -u +%FT%TZ)"`로 한 번만 다시 맡긴다.
- 미국 휴장일이면(날짜가 어제 그대로) 더 커밋하지 말고 "오늘은 미국 휴장" 한 줄로 끝낸다.

## 3. 웹 지표 보충 (3분) — Opus → `data/manual.json`
원칙: **매일 나오지 않는 값은 나온 날 반영하고, 그 전까지는 가장 최근 발표값을 그대로 쓴다** (화면에 기준일이 자동 표시됨).
curl로 봇 차단을 우회하지 않는다. 못 찾으면 비워 두고 넘어간다.
- **fg** (CNN 공포탐욕): CNN 사이트는 robots.txt로 자동 수집을 금지하므로 직접 열지 않는다. 웹검색으로 보도된 최근 값을 찾는다 (예: `"Fear & Greed" Benzinga "current reading"` → "At a current reading of N ... on <요일>"). 기사의 요일로 기준 날짜를 정해 `{"date": "<미국 날짜>", "value": N, "src": "Benzinga (CNN 인용)"}` 추가. 같은 날짜가 이미 있으면 건너뛴다.
- **pc** (매일): WebFetch `https://www.cboe.com/us/options/market_statistics/daily/?dt=<날짜>` 의 TOTAL PUT/CALL RATIO.
- **aaii** (목요일 발표): 강세%, 약세%, spread=강세−약세. date는 발표일(목).
- **margin** (월 1회): WebFetch `https://ycharts.com/indicators/finra_margin_debt` → 최신 월이 manual.json의 마지막 월보다 새로우면 `{"month": "YYYY-MM", "value": 백만달러, "yoy": YCharts 전년비%, "src": "YCharts (FINRA 원자료)"}` 추가.
- 바꿨으면 manual.json을 커밋하면서 `echo "--no-board $(date -u +%FT%TZ)" > .github/triggers/collect` 로 다시 맡긴다(끝나면 `git pull`).
- finviz는 요청이 많으면 일시 차단되므로 collect.py 외에 finviz를 따로 호출하지 않는다.

## 4. 웹 사실 조사 (2~3분) — Opus → `data/raw/research_<날짜>.json`
해석은 하지 않고 **확인된 사실만** 짧게 적는다 (한국어, 숫자 포함, 출처·주소 필수). 검색은 한 번에 병렬로.
먼저 `python3 scripts/brief.py` 를 한 번 실행해 오늘 대표 신고가·강세주·약세주와 `대표_신고가_이전코멘트`를 확인한다.
- **news**: 그날(미국 날짜) 시장 전체 흐름 기사 3~6건. 지수 등락의 보도된 이유, 큰 경제지표·연준 발언, 업종 이슈 등 (카드뉴스가 최대 8장이라 재료가 넉넉하면 좋다).
- **movers**: S&P500 강세주·약세주 상위 3개씩과 시총 상위 중 ±3% 이상 움직인 종목 — 그날 날짜 기사로 원인이 확인된 것만. 못 찾으면 넣지 않는다.
- **earnings**: 대표 신고가 중 `대표_신고가_이전코멘트`가 없거나, 그 뒤에 새 실적이 나온 종목만. 최근 분기 공시·보도자료의 매출·EPS·가이던스.
- **notes**: 못 구한 값, 이전 값을 유지한 지표 등.
```json
{
 "date": "<YYYY-MM-DD>",
 "news": [{"fact": "…", "src": "Reuters", "url": "https://…", "pub": "<기사 날짜>"}],
 "movers": {"<티커>": {"fact": "…", "src": "…", "url": "…"}},
 "earnings": {"<티커>": {"facts": ["3Q 매출 $134억 (+7%), 물량 +5%", "연간 가이던스 상향"], "src": "회사 3Q 실적 발표 (10/21)", "url": "…"}},
 "notes": ["공포탐욕 오늘 값 보도 없음 → 11/5 값 유지"]
}
```

## 5. 자료 묶음 (10초) — Opus
```
python3 scripts/brief.py        # → data/raw/brief_<날짜>.json (research 포함, 커밋 안 됨)
```

## 6. 해석·편집 (4~6분) — Fable
하위 에이전트를 **하나** 띄운다 (끝날 때까지 기다림):
```
Agent(subagent_type: "general-purpose", model: "fable", description: "Seoks 해석·편집", run_in_background: false,
      prompt: "당신은 Seoks 증시현황판의 해석·편집 담당입니다. /home/claude/seoks/FABLE.md 를 읽고 그대로 따르세요.
               날짜: <YYYY-MM-DD>. 자료 묶음: /home/claude/seoks/data/raw/brief_<YYYY-MM-DD>.json.
               할 일: data/comments/<YYYY-MM-DD>.json 작성·편집(총평·행동 가이드·시나리오 포함, 카드 4~8장), data/notes/companies.json 회사 설명 추가, check_comments.py 자체 검사.
               독자는 초보입니다. 좋다/나쁘다, 사기/기다리기/줄이기, 조심할 것을 숫자 기준과 함께 분명하게 쓰세요.
               웹검색은 하지 말고 자료 묶음의 사실·숫자만 쓰세요. 끝나면 FABLE.md 6절 형식으로 짧게 보고하세요.")
```
- 결과 파일: `data/comments/<날짜>.json`, `data/notes/companies.json` (추가분).
- Fable을 쓸 수 없으면(모델 오류 등) Opus가 `FABLE.md`대로 직접 쓰고, 마지막 메시지에 "Fable 사용 불가 → Opus 작성" 한 줄을 붙인다.

## 7. 검사 (1분) — Opus
```
python3 scripts/check_comments.py <날짜>
```
- `errors`가 있거나 `unverified_numbers`가 남아 있으면 **SendMessage로 같은 Fable 에이전트에** 검사 결과를 보내 고치게 한다 (한 번만).
- 그래도 남으면 Opus가 최소한만 손댄다: JSON 형식 오류만 고치고, 근거를 찾을 수 없는 숫자가 든 구절은 지운다(새 문장을 쓰지 않음). 마지막 메시지에 "검사 경고 n건 정리" 한 줄.
- 숫자를 고치기 전에는 Opus가 직접 자료(board·series·research)를 확인한다. 계산값(예: 453÷75≈6배)이 맞으면 그대로 둔다.

## 8. 저장 (1분) — Opus
```
python3 scripts/export_db.py      # 날짜별 기록 DB(data/db.csv) 갱신 → 구글 시트 'Seoks 날짜별 기록'이 자동으로 읽음
git pull -q --rebase   # GitHub 작업이 먼저 올린 data를 받는다
git add data && git commit -m "data: <날짜>" && git -c push.negotiate=true push
```
(`data/raw/`는 .gitignore 대상이라 자료 묶음·사실 조사 파일은 올라가지 않는다.)
GitHub Pages가 1분 안에 반영한다: https://hangseokemail-spec.github.io/seoks/

## 9. 다른 사람들 휴대폰 알림 (OneSignal 웹 푸시) — Opus가 GitHub 작업에 맡김
`data/notify/latest.json`에 제목·내용을 쓰고(`<...>` 채우기), 위 '맡기는 법'대로 `echo "send $(date -u +%FT%TZ)" > .github/triggers/notify` 와 함께 **한 번만** 푸시한다.
```json
{"date": "<YYYY-MM-DD>", "heading": "Seoks <M/D> 마감", "contents": "풍향계 <n> <구간> · <wind.verdict>",
 "url": "https://hangseokemail-spec.github.io/seoks/"}
```
- 끝나면 `git pull` 후 `data/notify/result.json`을 본다(`status`, `id`, `errors`).
- `errors`가 있으면 재시도하지 말고 마지막 메시지에 "다른 사람 알림 발송 실패: <이유>" 한 줄을 붙인다.
- 구독자가 없으면 "not subscribed" 오류가 오는데, 실패가 아니니 그대로 넘어간다.

## 10. 마지막 메시지 (= 선생님 휴대폰 Claude 알림) — Opus
300자 이내, 이 형식 그대로:
```
Seoks <M/D> 마감 | 풍향계 <n> <구간> | S&P <±x.xx%> 나스닥 <±x.xx%> | 트렌드캐치 <x.x> <판단> · 유동성 <x.x> <판단>
총평: <wind.verdict>
조심: <wind.guide.watch>
https://hangseokemail-spec.github.io/seoks/
```
문제가 있었으면(지표 누락, 재시도, 알림 실패, Fable 사용 불가 등) 한 줄 덧붙인다.
