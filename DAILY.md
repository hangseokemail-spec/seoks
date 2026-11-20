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
| 7~10 | **Opus 5.5** (메인 세션) | 검사 · 저장 · 다른 사람 알림 · 지침서 동기화 · 마지막 메시지 |

- **가중치**(트렌드캐치·유동성 지표 비중, 풍향계 심리·유동성 비중)는 `data/weights.json`이 정하고, 매주 토요일 별도 예약 작업(주간·월간·분기 점검)에서 **가장 최신 Claude 모델(지금 Fable 5.2)만** 결정하고 Opus가 적용한다(`WEIGHTS.md`). 매일 작업에서는 가중치를 건드리지 않는다. 풍향계 식은 brief의 `rules.풍향계_식`을 따른다.
- **작업 지침서**: 지침 파일(`GUIDE.md`·`DAILY.md`·`FABLE.md`·`WEIGHTS.md`)이나 가중치가 바뀌면 구글 드라이브 'AI › 증시현황판' 폴더의 지침서를 새 판으로 바꾼다(`GUIDE.md` 7절). 지침을 고친 세션은 그 자리에서, 매일 작업은 9-1단계에서 확인한다.
- 메인 세션이 Opus 5.5(`claude-opus-5-5`)가 아니면: 2~5단계를 `Agent(model: "opus")` 하나에, 7~9단계를 또 다른 `Agent(model: "opus")` 하나에 맡기고 메인 세션은 순서만 진행한다.
- Opus는 코멘트 **문장 내용**을 쓰거나 고치지 않는다 (7단계의 예외만). 사실(숫자·뉴스·실적)은 Opus가 모으고, 그 사실로 무엇을 말할지는 Fable이 정한다.

## 1. 준비 (1분) — Opus
1. 저장소 연결: `hangseokemail-spec/seoks` (push 권한). `git clone --depth 1 https://github.com/hangseokemail-spec/seoks /home/claude/seoks`
2. `pip install pandas numpy holidays --break-system-packages -q` (없을 때만)
3. `python3 scripts/usday.py` → 이번 작업의 미국 날짜(`us_date`)·휴장 여부(`trading`)·웹 지표 중 오늘 있어야 할 기준일(`due`)·빠진 지표(`missing`).
   - `trading: false`면 아무것도 커밋하지 않고 "오늘은 미국 휴장" 한 줄로 끝낸다(선생님 지시: 미국장이 쉬면 발간하지 않음).

> **진행 순서 (선생님 지시 2026-11-21): 1 → 3 → 2 → 4 → 5 …**
> 웹 지표(3단계)를 **먼저** 채우고, 빠진 값이 없을 때만 2단계 수집을 맡긴다. 수집이 끝나면 사이트 숫자가 바로 바뀌므로, 값이 빠진 채로 현황판이 올라가지 않게 하려는 순서다.
> 원칙은 **정해진 시각(06:20 전후)에 발간**이다. 값을 끝내 못 찾아 발간을 멈추는 일은 마지막 수단이다(3단계 4)).

## 2. 수집 (2~3분) — Opus가 GitHub 작업에 맡김 · **3단계를 마친 뒤에**
- 3단계에서 바꾼 `data/manual.json`을 같은 커밋에 넣어, 위 '맡기는 법'대로 `echo "run $(date -u +%FT%TZ)" > .github/triggers/collect` 를 푸시한다. GitHub 작업이 비밀값으로 `scripts/collect.py`와 이어서 `scripts/analyze.py`(지표 예측력 분석)를 돌리고 `data/`를 커밋한다.
- 끝나면 `git pull` 후 `data/runs/collect_last.json`을 본다: `result.date`가 오늘 미국 날짜이고 `result.board: true`면 정상. `log_tail`에 진행 기록이 있다.
- `finviz 날짜와 지수 날짜가 달라 현황판 생략`이면 5분 기다렸다 `echo "--force-board $(date -u +%FT%TZ)"`로 한 번만 다시 맡긴다.
- `result.date`가 `us_date`보다 이르면(휴장 목록에 없는 임시 휴장 등) 더 커밋하지 말고 "오늘은 미국 휴장" 한 줄로 끝낸다.

## 3. 웹 지표 보충 (3분) — Opus → `data/manual.json`
원칙: **매일 나오지 않는 값은 나온 날 반영하고, 그 전까지는 가장 최근 발표값을 그대로 쓴다** (화면에 기준일이 자동 표시됨).
**오늘 채울 값** = 1단계 `usday.py`의 `missing`(지표별 `due` 기준일보다 오래된 것). `missing`이 비어 있으면 3단계는 건너뛴다(장중 값을 마감 값으로 바꾸는 일만 할 수 있으면 한다).
순서 (선생님 지시 2026-11-21): **1) 자체 조사**로 찾고 → 공포탐욕·풋콜·신용융자 중 못 찾은 것은 **2) 구글 드라이브 '수치 조사_gemini'** 시트 → 그래도 없는 값은 **3) 조사 범위를 넓혀 다시** 찾고 → 정말 못 찾을 때만 **4) 선생님께 알리고 발간을 멈춘다.**

**1) 자체 조사 — 값이 빠지지 않게 지표마다 출처를 여러 곳 둔다.** 아래 순서대로 시도하고, 한 곳이 안 열리면 같은 주소를 다시 열지 말고 바로 다음 출처로 넘어간다. 검색은 한 번에 병렬로.
- **주소는 먼저 웹검색으로 찾고, 검색 결과에 나온 주소를 그대로 연다.** 예약 작업에서 직접 만든 주소(예: Cboe `?dt=<날짜>`)는 승인 대기로 막힌다(11/20에 Cboe·YCharts가 이렇게 막힘).
- 사이트가 자동 읽기를 거부하면(CNN 등) 다른 도구·브라우저·다른 AI로 우회하지 않는다. curl로 봇 차단을 우회하지 않는다. 남의 화면을 그대로 옮겨 보여 주는 복사 사이트(미러)도 쓰지 않는다. 그 값을 보도한 기사, 공식 통계, 데이터 제공사를 쓴다.
- 웹페이지를 여는 하위 에이전트(web-fetch)가 사용 한도 오류를 내면 `model: "opus"`로 다시 띄운다.
- **fg** (CNN 공포탐욕, 매일): CNN 페이지는 직접 열지 않는다. CNN 값을 숫자로 인용한 기사를 찾는다. 검색어 예: `"Fear & Greed" index <Month D> <YYYY>`, `"CNN Fear & Greed" falls OR rises`.
  1. Benzinga 장 요약 ("At a current reading of N ... on <요일>")
  2. TokenPost 투자 뉴스 ("CNN Fear & Greed Index Falls to N" — 11/20 확인)
  3. 그 밖에 CNN 값을 숫자로 인용한 경제 기사 (CNBC·Yahoo Finance·MarketWatch·Fox Business·Investopedia·Finwire 등)
  기사 날짜·요일로 기준 날짜를 정해 `{"date": "<미국 날짜>", "value": N, "src": "<매체> (CNN Fear & Greed 인용[, 장중])"}` 추가. 장중 값이면 src에 '장중'을 적고, 같은 날짜의 마감 값을 찾으면 그것으로 바꾼다. 같은 날짜가 이미 있으면 건너뛴다.
- **pc** (Cboe 전체 풋콜비율, 매일, 하루 늦게 공개):
  1. YCharts `CBOE Total Put/Call Ratio` (ycharts.com/indicators/total_putcall_ratio) — 날짜별 표가 있어 빠진 날도 채울 수 있다 (11/20 확인)
  2. Cboe 일간 통계 페이지 (검색 결과 주소)
  3. thetrading.tools put-call-ratio (Cboe 원자료, 하루~며칠 늦음)
  어제 값이 아직 없으면 나와 있는 가장 최근 날짜까지 채운다. `{"date": "<미국 날짜>", "value": x.xx, "src": "<출처> (Cboe 원자료)"}`
- **aaii** (목요일 발표): 강세%, 약세%, spread=강세−약세. date는 발표일(목). 구글 시트에 없는 값이라 출처를 넓게 둔다.
  1. AAII 공식 Sentiment Survey 페이지
  2. YCharts `US Investor Sentiment, % Bullish` · `% Bearish` (날짜별 표)
  3. 결과를 인용한 기사 (검색어 `AAII sentiment survey <Month D>`, `AAII bullish bearish <Month D>` — Investing.com·MarketWatch·Seeking Alpha·Yahoo Finance·Nasdaq.com 등)
  4. 한국어 기사 (검색어 `AAII 투자심리 <M월 D일>` — 연합인포맥스·뉴스핌·한경 등)
- **margin** (신용융자, 월 1회, 다음 달 셋째 주 공개):
  1. FINRA 공식 Margin Statistics (finra.org/investors/margin-statistics) — 백만 달러 정확값. 1년 전 같은 달 값도 표에 있어 전년비를 직접 계산한다 (11/20 확인)
  2. YCharts `finra_margin_debt` (전년비 표기값 있음)
  3. thetrading.tools margin-debt (FINRA 원자료, 조 단위 반올림)
  최신 월이 manual.json의 마지막 월보다 새로우면 `{"month": "YYYY-MM", "value": 백만달러, "yoy": 전년비%, "src": "<출처>"}` 추가.

**2) 자체 조사로 못 찾은 지표는 구글 드라이브 '수치 조사_gemini'에서 확인한다.** 'AI › 증시현황판' 폴더(id `1Naz2cTUd4SCknOTXroSLgvujROrxPRpU`)의 구글 시트 '수치 조사_gemini'(id `1A87drnPjcDJtBT1ryaOjOO0WYATT8yKmNwr9hdQGNbA`), '일별 기록' 탭. 매일 오전 6시경 한 줄씩 기록된다. 구글 드라이브 `read_file_content`로 읽는다.
- 열: 수집일자(KST) · Fear & Greed 지수·등급·기준일(ET) · Total Put/Call · Equity Put/Call · Put/Call 기준일(ET) · Margin Debt 당월 잔액($M) · 전년동월 잔액($M) · YoY · 기준월 · 비고.
- 수집일자가 오늘(KST)인 줄에서 필요한 칸만 쓴다: fg = 지수(date = F&G 기준일), pc = Total Put/Call(date = Put/Call 기준일), margin = 당월 잔액·YoY(month = 기준월). src는 `"수치 조사_gemini (구글 드라이브)"`. 기준일이 manual.json의 마지막 값보다 새로울 때만 넣는다.
- 오늘 줄이 아직 없으면(06:04 작업이 여기 닿는 06:10 전후에 아직 기록 전일 수 있음) 3)을 하면서 **3분마다 다시 확인한다(06:30까지)**. 그 사이 생기면 그 값을 쓴다.

**3) 조사 범위를 넓혀 다시 찾는다.** 2)까지 와도 빠진 값(특히 시트에 없는 AAII)은
- 위 목록에서 아직 안 연 출처를 모두 연다. 검색어를 바꿔(영어·한국어, `Nov 20`·`November 20, 2026`·`11/20` 같은 날짜 표기, 지표의 다른 이름) 최소 2번 더 찾는다.
- 그날 값을 숫자로 인용한 기사·데이터 제공사·공식 통계면 쓸 수 있다(src에 매체 이름, 장중이면 '장중'). 기준일이 `due`와 맞아야 한다.
- 2)의 시트를 마지막으로 한 번 더 본다.

**4) 정말 못 찾을 때만 — 선생님께 알리고 발간을 멈춘다.** (선생님 지시 2026-11-21: "정 못찾는 경우에만 나한테 알림 보내고 현황판 발간을 멈춰. 그러면 내가 알림 보고 수치 찾아서 넣어줄께. 다만 그런 경우는 가능하면 없으면 좋겠고, 정해진 시간에 발간이 되면 좋겠어.")
- 2단계 수집을 맡기지 않는다(사이트는 전날 판 그대로). 아무것도 커밋하지 않는다. 다른 사람 알림(9단계)도 보내지 않는다.
- `PushNotification`으로 알린다(200자 안). 그리고 같은 내용을 마지막 메시지로 쓰고 이 대화에서 선생님 답을 기다린다(턴을 끝낸다):
  `Seoks <M/D> 발간 보류 — 못 찾은 값: <지표>(<기준일>)[, …] · 시도: <출처들>·gemini 시트 · 값을 이 대화에 답장하거나 '수치 조사_gemini' 시트에 적어 주시면 바로 발간합니다`
- 선생님이 답하면: 답장 값(또는 시트에 새로 적힌 값)을 manual.json에 넣고(src `"선생님 입력 (<날짜>)"`) 2단계부터 이어서 끝까지 한다. 마지막 메시지에 "선생님 입력 값으로 늦게 발간" 한 줄을 붙인다.
- 원칙은 정해진 시각 발간이다. 4)로 가기 전에 1)~3)을 빠짐없이 했는지 확인한다.
- finviz는 요청이 많으면 일시 차단되므로 collect.py 외에 finviz를 따로 호출하지 않는다.

## 4. 웹 사실 조사 (2~3분) — Opus → `data/raw/research_<날짜>.json`
해석은 하지 않고 **확인된 사실만** 짧게 적는다 (한국어, 숫자 포함, 출처·주소 필수). 검색은 한 번에 병렬로.
먼저 `python3 scripts/brief.py` 를 한 번 실행해 오늘 대표 신고가·강세주·약세주와 `대표_신고가_이전코멘트`를 확인한다.
**기사도 출처를 여러 곳 둔다.** 한 매체가 안 열리면 같은 내용을 다룬 다른 매체로 바로 넘어간다 (11/20에 CNBC·Investing.com·GuruFocus가 막힘).
- 시장 전체: Reuters (GV Wire·Fidelity 뉴스 등에 실린 글 포함) → AP (Inquirer 등에 실린 글 포함) → Yahoo Finance → Motley Fool·MarketWatch·Investopedia
- 종목 원인: Yahoo Finance → Seeking Alpha 뉴스 → Motley Fool "Why ... stock" → Reuters·AP 기사 안의 종목 언급 → 회사 보도자료
- 실적: 회사 보도자료(Business Wire·PR Newswire 재게재 포함) → SEC 8-K → 실적 기사
- 장중 기사 숫자는 종가로 쓰지 않는다. 지수·종목 종가는 현황판(collect 결과)을 기준으로 한다.
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

## 9-1. 지침서 동기화 (1분) — Opus
알림을 보낸 **뒤에** 한다(발간을 늦추지 않게). `GUIDE.md` 7절 그대로:
```
python3 scripts/guide_export.py build      # "changed": false 면 끝
```
- `"changed": true`면 구글 드라이브 `create_file`(title·parentId=folder_id·contentMimeType "text/html"·base64Content=file_ref) → `prev_doc_id`가 있으면 `update_file`(fileId=prev_doc_id, title=prev_title_new, parentId=old_folder_id) → `python3 scripts/guide_export.py done <새 문서 id>` → `git add data/guide_sync.json && git commit -qm "지침서 동기화" && git pull -q --rebase && git push -q`.
- 이전 판은 지우지 않는다. 구글 드라이브에 닿지 않으면 건너뛰고 마지막 메시지에 "지침서 갱신 못 함" 한 줄.

## 10. 마지막 메시지 (= 선생님 휴대폰 Claude 알림) — Opus
300자 이내, 이 형식 그대로:
```
Seoks <M/D> 마감 | 풍향계 <n> <구간> | S&P <±x.xx%> 나스닥 <±x.xx%> | 트렌드캐치 <x.x> <판단> · 유동성 <x.x> <판단>
총평: <wind.verdict>
조심: <wind.guide.watch>
https://hangseokemail-spec.github.io/seoks/
```
문제가 있었으면(지표 누락, 재시도, 알림 실패, Fable 사용 불가 등) 한 줄 덧붙인다.
