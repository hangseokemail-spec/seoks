# Seoks 증시현황판

매일 아침 미국 증시를 정리하는 현황판입니다. https://hangseokemail-spec.github.io/seoks/

- **증시현황판**: 3대 지수, 시장 Breadth, 52주 신고가 업종 분포, 대표 신고가 8선(BM·실적·포인트·주의)
- **트랜드캐치**: 시장 심리 9개 지표 → 1~5점 → 단순평균 (광기·과열·중립·불안·공포)
- **유동성**: 유동성 11개 지표 → 1~5점 → 가중평균 (풍부·우호·중립·긴축·경색)
- 날짜 칩·달력으로 과거 보기, 모든 수치는 눌러서 계산 방법 확인, 나스닥100·S&P500·코스피와의 상관

## 구조
- `scripts/collect.py` — finviz Elite, 네이버 증권, FRED에서 수집해 `data/`에 JSON 생성 (키는 환경변수, 저장소에 없음)
- `data/manual.json` — 웹에서 확인하는 지표(CNN F&G, AAII, Cboe Put/Call, FINRA 신용융자)
- `data/comments/` — 매일 Claude가 쓰는 코멘트
- `DAILY.md` — 매일 아침 Claude 예약 작업 절차
- `apps-script/Code.gs` — 구글 시트 기록·구독자 메일

공개 데이터를 자동으로 모아 계산한 참고 자료이며 투자 권유가 아닙니다.
