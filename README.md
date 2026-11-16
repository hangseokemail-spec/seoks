# Seoks 증시현황판

매일 아침 미국 증시를 정리하는 현황판입니다. https://hangseokemail-spec.github.io/seoks/

- **증시현황판**: 3대 지수, 시장 Breadth, 52주 신고가 업종 분포, 대표 신고가 8선(BM·실적·포인트·주의)
- **트렌드캐치**: 시장 심리 9개 지표 → 1~5점 → 가중평균 (광기·과열·중립·불안·공포)
- **유동성**: 유동성 11개 지표 → 1~5점 → 가중평균 (풍부·우호·중립·긴축·경색)
- 날짜 칩·달력으로 과거 보기, 모든 수치는 눌러서 계산 방법 확인, 나스닥100·S&P500·코스피와의 상관

## 구조
- `scripts/collect.py` — finviz Elite, 네이버 증권, FRED에서 수집해 `data/`에 JSON 생성 (키는 환경변수, 저장소에 없음)
- `scripts/analyze.py` — 지표별 예측력(선행·후행) 분석 → `data/analysis.json`
- `data/manual.json` — 웹에서 확인하는 지표(CNN F&G, AAII, Cboe Put/Call, FINRA 신용융자)
- `data/comments/` — 매일 Claude가 쓰는 코멘트 (해석·편집 = Claude Fable)
- `DAILY.md` — 매일 아침 Claude 예약 작업 절차 (수집·계산·검사·커밋·알림 = Claude Opus 5.5, 해석·편집 = Claude Fable)
- `FABLE.md` — 해석·편집 담당(Fable) 지침
- `scripts/brief.py` — Fable에게 넘길 자료 묶음(`data/raw/brief_<날짜>.json`, 커밋 안 됨)
- `scripts/check_comments.py` — 코멘트 형식·숫자 대조 검사
- `scripts/export_db.py` — 날짜별 기록 DB `data/db.csv` (구글 시트 'Seoks 날짜별 기록'이 IMPORTDATA로 읽음)
- `data/weights.json` — 지표 가중치와 풍향계 심리·유동성 비중의 버전 기록(적용 시작일별). 매주 토요일 점검(주간·월간·분기, 조정 폭 분기 > 월간 > 주간) — **가장 최신 Claude 모델**(지금 Fable 5.2)이 결정, Opus가 적용
- `scripts/weights.py` — 가중치 버전을 읽어 종합 점수·풍향계 계산 (collect.py·wind.py·brief.py가 사용)
- `scripts/weights_eval.py` / `WEIGHTS.md` — 가중치 점검: 근거 자료(brief: 풍향계 방향 적중 점검 + 지표별 관계) → 결정 모델이 후보 시험·결정 → Opus가 그대로 적용(apply)
- `scripts/backfill_sp500_ma.py` — S&P500 50·200일선 위 비율 과거값(2017~)을 구성종목 일봉으로 계산 (한 번만 실행)
- `apps-script/Code.gs` — 구글 시트 기록·구독자 메일

공개 데이터를 자동으로 모아 계산한 참고 자료이며 투자 권유가 아닙니다.
