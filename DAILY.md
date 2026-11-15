# Seoks 매일 아침 작업 절차 (Claude 예약 작업용)

미국 정규장 마감 직후(뉴욕 16:04, 한국 06:04 겨울 / 05:04 여름) 실행한다.
목표: **한국 시각 06:15 전후에 알림**. 빠르게, 그러나 숫자는 정확하게.
API 키(FINVIZ_AUTH, FRED_KEY, ONESIGNAL_KEY)는 예약 작업 프롬프트로 전달된다. **키를 파일·커밋·메시지에 절대 쓰지 않는다.**

## 1. 준비 (1분)
1. 저장소 연결: `hangseokemail-spec/seoks` (push 권한). `git clone --depth 1 https://github.com/hangseokemail-spec/seoks /home/claude/seoks`
2. `pip install pandas numpy --break-system-packages -q` (없을 때만)

## 2. 수집 (2분)
```
cd /home/claude/seoks
FINVIZ_AUTH=... FRED_KEY=... python3 scripts/collect.py
```
- 마지막 줄 JSON의 `date`가 오늘 미국 날짜이고 `board: true`면 정상.
- `finviz 날짜와 지수 날짜가 달라 현황판 생략`이면 5분 기다렸다 `--force-board`로 한 번만 다시 실행.
- 미국 휴장일이면(날짜가 어제 그대로) 커밋하지 말고 "오늘은 미국 휴장" 한 줄로 끝낸다.
- 이어서 `FINVIZ_AUTH=... FRED_KEY=... python3 scripts/analyze.py` (지표 예측력 분석 갱신, 20초 안팎).

## 3. 웹 지표 보충 (3분) → `data/manual.json`
원칙: **매일 나오지 않는 값은 나온 날 반영하고, 그 전까지는 가장 최근 발표값을 그대로 쓴다** (화면에 기준일이 자동 표시됨).
curl로 봇 차단을 우회하지 않는다. 못 찾으면 비워 두고 넘어간다.
- **fg** (CNN 공포탐욕): CNN 사이트는 robots.txt로 자동 수집을 금지하므로 직접 열지 않는다. 웹검색으로 보도된 최근 값을 찾는다 (예: `"Fear & Greed" Benzinga "current reading"` → "At a current reading of N ... on <요일>"). 기사의 요일로 기준 날짜를 정해 `{"date": "<미국 날짜>", "value": N, "src": "Benzinga (CNN 인용)"}` 추가. 같은 날짜가 이미 있으면 건너뛴다.
- **pc** (매일): WebFetch `https://www.cboe.com/us/options/market_statistics/daily/?dt=<날짜>` 의 TOTAL PUT/CALL RATIO.
- **aaii** (목요일 발표): 강세%, 약세%, spread=강세−약세. date는 발표일(목).
- **margin** (월 1회): WebFetch `https://ycharts.com/indicators/finra_margin_debt` → 최신 월이 manual.json의 마지막 월보다 새로우면 `{"month": "YYYY-MM", "value": 백만달러, "yoy": YCharts 전년비%, "src": "YCharts (FINRA 원자료)"}` 추가.
- 바꿨으면 `python3 scripts/collect.py --no-board` 다시 실행.
- finviz는 요청이 많으면 일시 차단되므로 collect.py 외에 finviz를 따로 호출하지 않는다.

## 4. 코멘트 (5~7분) → `data/comments/<날짜>.json`
형식은 `data/comments/2026-11-13.json`과 같다. 한국어, 초보자도 이해하게, 숫자로. **확인 안 된 내용은 쓰지 않는다.**
풍향계 값은 collect.py 마지막 출력의 `풍향계 {"wind":.., "zone":..}`와 `data/wind.json`에서 읽는다 (계산식: 65 − 15×트렌드캐치 + 10×유동성).
- `wind.headline`: 풍향계 점수·구간·한 줄 판단 (60자 안팎). 새 소식·알림에 쓰인다.
- `wind.points`: 3개 `{h, t}`. h = 한 줄 핵심(20자 안팎), t = 2~3문장 근거.
  ① 지금 구간과 1주 전 대비 변화 ② 시장 속(Breadth·섹터)이 말하는 것 ③ 앞으로 볼 것(어떤 숫자가 어떻게 되면 순풍/역풍으로 바뀌는지).
- `market.headline` (= `oneliner`에도 같은 값): 45자 안팎. "무슨 일 · 핵심 숫자".
- `market.cards`: 카드뉴스 4~5장 `{tone, tag, title, num, back}`.
  - tone: `up`(좋은 소식, 초록) / `down`(나쁜 소식, 빨강) / `flat`(애매·엇갈림, 회색). 주식시장에 좋은지 나쁜지 기준으로 일관되게.
  - tag 8자 안팎, title 20자 안팎(앞면 큰 글씨), num = 핵심 숫자 하나, back = 뒷면 2~3문장(숫자·확인된 사실).
  - 보통 구성: 그날 가장 큰 변화(업종·종목) / 강한 쪽 / 시장 체력(신고가·신저가·200일선) / 지수 흐름 / 심리·유동성.
  - 뉴스는 그날 날짜 기사를 웹검색으로 확인한 것만. 개별 종목 급등락 원인을 확인 못 했으면 짐작하지 말고 "원인은 확인된 보도가 없어 적지 않음".
- `market.news`, `market.leaders`: 예전 형식(없어도 됨, 있으면 유지).
- `tc_summary`, `lq_summary`: 종합 카드 아래 '종합의견' 1~2문장. 점수·라벨·무엇이 올리고 내리는지.
- `tc_points`, `lq_points`: 3개 `{h, t}`. ① 무엇을 알 수 있나 ② 왜 봐야 하나(근거 숫자, analysis.json의 순위상관 등) ③ 무엇을 할까/조심할까(어떤 점수·숫자가 되면 무엇을 검토하는지 기준 제시).
  판단 보조로 쓰되 단정적인 매수·매도 지시는 피한다 ("~을 검토할 때", "~을 줄이는 편이 낫다").
- `tc`, `lq`: 예전 형식 2~3문장(풍향계 카드 fallback용, 유지).
- `quad`: 사분면 판단 보조 2~3문장. 보이는 움직임을 다시 묘사하지 말고, 지금 칸이 행동으로 무엇을 뜻하는지와 어느 선을 넘으면 무엇을 검토할지.
- `features`: board의 `features`(S&P500 신고가, 최대 9개) 각각 `tag`(10자 안팎), `bm`, `e1`, `e2`(최근 실적·신고가 배경), `point`, `caution`.
  - 실적은 최근 분기 공시·보도자료를 웹검색으로 확인한다. 여러 종목 검색은 한 번에 병렬로.
  - 당일 상승의 원인을 단정하지 않는다.
- `data/notes/companies.json`: board의 `top40`·`gainers`·`losers`·`mega`·`features` 종목 중 `desc`가 없는 종목에 한 줄 설명(20자 안팎, 무슨 회사인지)을 추가한다.
  - 확실히 아는 회사만 직접 쓰고, 모르면 업종(`ind`)과 국가를 우리말로 옮겨 쓴다 (예: "미국 지역은행"). 지어내지 않는다.

## 5. 저장 (1분)
```
git add data && git commit -m "data: <날짜>" && git -c push.negotiate=true push
```
GitHub Pages가 1분 안에 반영한다: https://hangseokemail-spec.github.io/seoks/

## 6. 다른 사람들 휴대폰 알림 (OneSignal 웹 푸시)
`ONESIGNAL_KEY`는 예약 작업 프롬프트로 전달된다. 제목·내용의 `<...>`를 채워 한 번만 보낸다.
```
curl -sS -X POST "https://api.onesignal.com/notifications?c=push" \
  -H "Authorization: Key $ONESIGNAL_KEY" -H "Content-Type: application/json" \
  -d '{"app_id":"c323691f-5bf6-4942-aac1-fd6254f1b0c0","target_channel":"push","included_segments":["Total Subscriptions"],
       "headings":{"en":"Seoks <M/D> 마감","ko":"Seoks <M/D> 마감"},
       "contents":{"en":"<wind.headline>","ko":"<wind.headline>"},
       "url":"https://hangseokemail-spec.github.io/seoks/"}'
```
- 응답에 `errors`가 있으면 재시도하지 말고 마지막 메시지에 "다른 사람 알림 발송 실패: <이유>" 한 줄을 붙인다.

## 7. 마지막 메시지 (= 선생님 휴대폰 Claude 알림)
300자 이내, 이 형식 그대로:
```
Seoks <M/D> 마감 | 풍향계 <n> <구간> | S&P <±x.xx%> 나스닥 <±x.xx%> | 트렌드캐치 <x.x> <판단> · 유동성 <x.x> <판단>
<wind.headline>
https://hangseokemail-spec.github.io/seoks/
```
문제가 있었으면(지표 누락, 재시도, 알림 실패 등) 한 줄 덧붙인다.
