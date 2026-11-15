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

## 4. 코멘트 (5분) → `data/comments/<날짜>.json`
형식은 `data/comments/2026-11-13.json`과 같다. 한국어, 짧게, 숫자로. **확인 안 된 내용은 쓰지 않는다.**
- `market.headline` (= `oneliner`에도 같은 값): 45자 안팎. "무슨 일 · 핵심 숫자" 형식.
- `market.news`: 그날 가장 이슈가 된 기사·사건 1~2개. 그날 날짜의 기사를 웹검색으로 확인한 것만 쓴다.
  - 개별 종목 급등락의 원인을 기사로 확인하지 못했으면 원인을 짐작하지 말고 숫자만 쓴다.
- `market.leaders`: `data/board/<날짜>.json`의 `sector_perf`(섹터 시총가중 등락), `gainers`·`losers`(S&P500), `mega`(시총 상위)로 주도 섹터와 강한 기업을 한 줄로 정리한다. 이 숫자들은 그대로 옮긴다.
- `tc`, `lq`: 2~3문장. 어떤 지표가 점수를 올리고 내리는지, 빠진 지표가 있으면 그 사실.
- `quad`: 1~2문장. 사분면 위치와 다음에 볼 것.
- `features`: board의 `features`(S&P500 신고가, 최대 8개) 각각 `tag`(10자 안팎), `bm`, `e1`, `e2`(최근 실적·신고가 배경), `point`, `caution`.
  - 실적은 최근 분기 공시·보도자료를 웹검색으로 확인한다. 여러 종목 검색은 한 번에 병렬로.
  - 당일 상승의 원인을 단정하지 않는다. 투자 권유 표현(사라/팔아라)을 쓰지 않는다.
- `data/notes/companies.json`: board의 `top40`·`gainers`·`losers`·`mega`·`features` 종목 중 `desc`가 없는 종목에 한 줄 설명(20자 안팎, 무슨 회사인지)을 추가한다.
  - 확실히 아는 회사만 직접 쓰고, 모르면 finviz 업종(`ind`)과 국가를 우리말로 옮겨 쓴다 (예: "미국 지역은행"). 지어내지 않는다.

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
       "contents":{"en":"<market.headline>","ko":"<market.headline>"},
       "url":"https://hangseokemail-spec.github.io/seoks/"}'
```
- 응답에 `errors`가 있으면 재시도하지 말고 마지막 메시지에 "다른 사람 알림 발송 실패: <이유>" 한 줄을 붙인다.

## 7. 마지막 메시지 (= 선생님 휴대폰 Claude 알림)
300자 이내, 이 형식 그대로:
```
Seoks <M/D> 마감 | S&P <±x.xx%> 나스닥 <±x.xx%> | 신고가 <n> · 신저가 <n> | 트랜드캐치 <x.x> <판단> · 유동성 <x.x> <판단>
<market.headline>
https://hangseokemail-spec.github.io/seoks/
```
문제가 있었으면(지표 누락, 재시도, 알림 실패 등) 한 줄 덧붙인다.
