"""팩터 도서관(data/factor_library.json) 처음 만들기 — 2026-11-21 선생님 지시로 Opus가 논문을 찾아 정리.
이후에는 이 파일을 다시 돌리지 않고 data/factor_library.json을 직접 고칩니다(점검 세션이 후보·논문을 보탬).
"""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "factor_library.json")

D = lambda **k: k  # noqa: E731

papers = {
    "huang_kilic_2019": D(cite="Huang & Kilic (2019), Gold, platinum, and expected stock returns, Journal of Financial Economics 132(3)",
                          finding="금/백금 가격 비율(GP)이 미국 주식의 앞으로 수익률을 예측한다. 금이 백금보다 비싸질수록(위험 회피가 클수록) 이후 주식 수익률이 높았다.",
                          url="https://www.econbiz.de/Record/gold-platinum-and-expected-stock-returns-huang-darien/10012163951"),
    "hulbert_gp": D(cite="Hulbert(MarketWatch) 정리, 2024 — Huang·Kilic 결과를 2004년 이후로 다시 봄",
                    finding="금/백금 비율의 12개월 변화가 가장 큰 4분의 1일 때 다음 12개월 Wilshire 5000이 20.5%, 가장 작은 4분의 1일 때 6.5% 올랐다.",
                    url="https://finance.technews.tw/2024/02/05/gold-and-platinum-are-giving-strong-clues-that-stocks-could-gain-15-percent-or-more-this-year/"),
    "xu_li_singh_2023": D(cite="Xu, Li & Singh (2023), Does gold–platinum price ratio predict stock returns? International evidence, Int. J. Managerial Finance 19(2)",
                          finding="17개 선진국 시장(1978~2019 월별)에서 금/백금 비율의 수준보다 '변화'가 단기·장기 모두 더 강하게 예측했다.",
                          url="https://www.emerald.com/insight/content/doi/10.1108/IJMF-06-2020-0328/full/html"),
    "pham_rudolf_2021": D(cite="Pham & Rudolf (2021), Gold, platinum, and industry stock returns, Int. Review of Economics & Finance 75",
                          finding="금/백금 비율은 경기민감 업종을 방어 업종보다 잘 예측. 1개월 표본 외 예측은 약하지만 경제적으로 의미가 있었다.",
                          url="https://econpapers.repec.org/RePEc:eee:reveco:v:75:y:2021:i:c:p:252-266"),
    "gsr_tail_2022": D(cite="International Review of Financial Analysis (2022), 금/은·금/백금 비율과 선진국 증시 꼬리 위험(1세기 자료)",
                       finding="금/은 비율도 금/백금 비율처럼 세계 위험의 대리 변수로 움직였고, 증시 꼬리 위험(급락) 표본 외 예측에 자주 도움이 됐다.",
                       url="https://researcharchive.lincoln.ac.nz/signposting/describedby/6ed72691-c39a-442c-98e4-83de5052266f"),
    "jacobsen_2019": D(cite="Jacobsen, Marshall & Visaltanachoti (2019), Stock Market Predictability and Industrial Metal Returns, Management Science 65(7)",
                       finding="구리·알루미늄 같은 산업금속 가격 움직임이 주식 수익률을 예측한다. 경기 확장기엔 금속이 오르면 이후 주식에 나쁘고(1표준편차에 월 약 −1.5%), 침체기엔 좋다(약 +0.5%).",
                       url="https://pubsonline.informs.org/doi/pdf/10.1287/mnsc.2017.2933"),
    "driesprong_2008": D(cite="Driesprong, Jacobsen & Maat (2008), Striking oil: Another puzzle?, Journal of Financial Economics 89(2)",
                         finding="유가가 오르면 이후 주식 수익률이 크게 낮아진다. 투자자가 유가 정보에 늦게 반응하는 것으로 해석.",
                         url="https://econpapers.repec.org/RePEc:eee:jfinec:v:89:y:2008:i:2:p:307-327"),
    "yang_2024": D(cite="Yang (2024), Gold is a Hedging Asset, 북경대 PHBS 워킹페이퍼",
                   finding="log 금값 − log 유가(금/유가 비율)가 주식 수익률 예측 변수(연간 표본 내 R² 11%, 표본 외 14%). 금은 기대수익이 높아질 때 오르고 유가는 내린다는 해석.",
                   url="https://business.ucdenver.edu/jpmorgancenter/Node/588"),
    "gold_ratios_cep": D(cite="TU Chemnitz CEP005, 금 비율 10종(금/은·금/유가·금/구리 등)으로 금의 상대가치 분석",
                         finding="금/은·금/유가·금/구리 등 10가지 금 비율을 처음으로 체계적으로 비교. 불확실성이 커지면 금의 상대가격이 오른다(안전자산).",
                         url="https://www.tu-chemnitz.de/wirtschaft/vwl1/RePEc/download/tch/wpaper/CEP005_relative_valuation_gold.pdf"),
    "copper_gold_2024": D(cite="North American J. of Economics and Finance (2024), Copper-to-gold ratio as a leading indicator for the 10-Year Treasury yield",
                          finding="구리/금 비율은 미국 10년물 금리의 선행 지표. 주식에 대한 직접 근거는 약하다.",
                          url="https://ideas.repec.org/a/eee/ecofin/v69y2024ipas1062940823001390.html"),
    "sentimentrader_cg": D(cite="SentimenTrader (2024), 구리/금 비율 실전 점검",
                           finding="구리/금 비율이 여러 해 최저로 떨어진 뒤 S&P500은 오히려 1년간 강했다 — '경기 불안 신호'라는 통념과 반대.",
                           url="https://sentimentrader.com/blog/what-the-coppergold-ratio-is-suggesting-about-market-potential"),
    "btz_2009": D(cite="Bollerslev, Tauchen & Zhou (2009), Expected Stock Returns and Variance Risk Premia, Review of Financial Studies 22(11)",
                  finding="내재 변동성(VIX)² − 실현 분산(변동성 위험 프리미엄)이 높으면 이후 수익률이 높다. 분기 수익률에서 특히 강하고 P/E·신용 스프레드보다 낫다. 일별 대신 장중 자료로 실현 분산을 재야 가장 정확.",
                  url="https://econpapers.repec.org/RePEc:oup:rfinst:v:22:y:2009:i:11:p:4463-4492"),
    "jones_tuzel_2013": D(cite="Jones & Tuzel (2013), New Orders and Asset Prices, Review of Financial Studies 26(1)",
                          finding="내구재 신규주문/출하 비율(NO/S)이 높으면(경기 정점 근처) 이후 1개월~1년 주식·채권 초과수익률이 낮다.",
                          url="https://econpapers.repec.org/RePEc:oup:rfinst:v:26:y:2013:i:1:p:115-157"),
    "rrz_2016": D(cite="Rapach, Ringgenberg & Zhou (2016), Short interest and aggregate stock returns, Journal of Financial Economics 121(1)",
                  finding="시장 전체 공매도 잔고는 알려진 가장 강한 시장 수익률 예측 변수 중 하나(연간 표본 내 R² 12.89%, 표본 외 13.24%).",
                  url="https://econpapers.repec.org/RePEc:cuf:wpaper:716"),
    "bakshi_2011": D(cite="Bakshi, Panayotov & Skoulakis (2011), The Baltic Dry Index as a Predictor of Global Stock Returns",
                     finding="발틱 건화물 운임지수(BDI) 3개월 증가율이 다음 1~3개월 세계 주식·원자재 수익률을 양(+)으로 예측, 6개월이면 사라짐.",
                     url="https://www.cxoadvisory.com/economic-indicators/baltic-dry-index-as-return-predictor"),
    "gz_ebp": D(cite="Gilchrist & Zakrajšek (2012) / Favara·Gilchrist·Lewis·Zakrajšek (2016, 연준 FEDS Notes)",
                finding="회사채 스프레드 중 부도 위험으로 설명되지 않는 부분(초과 채권 프리미엄, EBP)은 회사채 시장의 위험 선호를 보여 주고 경기 침체를 예측한다. 연준이 매달 CSV로 공개.",
                url="https://www.federalreserve.gov/econres/notes/feds-notes/updating-the-recession-risk-and-the-excess-bond-premium-20161006.html"),
    "cooper_priestley_2009": D(cite="Cooper & Priestley (2009), Time-Varying Risk Premiums and the Output Gap, Review of Financial Studies 22(7)",
                               finding="산출 갭(산업생산의 장기 추세 대비 차이)이 표본 내·외에서 미국 주식 수익률을 예측. 가격이 들어가지 않은 경기 지표.",
                               url="https://academicnewsletter.sufe.edu.cn/info/355172"),
    "neely_2014": D(cite="Neely, Rapach, Tu & Zhou (2014), Forecasting the Equity Risk Premium: The Role of Technical Indicators, Management Science 60(7)",
                    finding="이동평균·모멘텀 같은 기술 지표가 거시 변수만큼 예측력이 있고 서로 보완한다. 기술 지표는 경기 정점 근처의 하락을, 거시 변수는 바닥 근처의 상승을 잘 잡는다.",
                    url="https://ink.library.smu.edu.sg/lkcsb_research_smu/147/"),
    "hong_2007": D(cite="Hong, Torous & Valkanov (2007), Do industries lead stock markets?, Journal of Financial Economics 83(2) / Tse (2015) 재검토",
                   finding="소매·금융·부동산·금속·석유 업종 수익률이 시장을 최대 2개월 앞선다(금속·석유는 반대 방향). 다만 2015년 재검토에서는 효과가 약해졌다.",
                   url="https://econpapers.repec.org/RePEc:cdl:anderf:qt6x49x543"),
    "gwz_2024": D(cite="Goyal, Welch & Zafirov (2024), A Comprehensive 2022 Look at the Empirical Performance of Equity Premium Prediction, Review of Financial Studies 37(11)",
                  finding="2008년 이후 논문의 새 변수 29개 + 기존 17개를 2021년까지 다시 보니, 새 변수의 3분의 1 넘게가 표본 내에서도 의미를 잃었고 남은 것의 절반은 표본 외 성적이 나빴다. 소수만 꾸준했다.",
                  url="https://econpapers.repec.org/RePEc:oup:rfinst:v:37:y:2024:i:11:p:3490-3557."),
    "mclean_pontiff_2016": D(cite="McLean & Pontiff (2016), Does Academic Research Destroy Stock Return Predictability?, Journal of Finance 71(1)",
                             finding="논문으로 발표된 예측 신호는 발표 뒤 효과가 줄어든다(투자자가 배워서). 논문 결과를 그대로 믿지 말고 최근 자료로 다시 확인해야 한다.",
                             url="https://econpapers.repec.org/RePEc:bla:jfinan:v:71:y:2016:i:1:p:5-32"),
    "rsz_2010": D(cite="Rapach, Strauss & Zhou (2010), Out-of-Sample Equity Premium Prediction: Combination Forecasts, Review of Financial Studies 23(2)",
                  finding="변수 하나로 예측하면 불안정하지만, 여러 변수의 예측을 섞으면(결합 예측) 표본 외에서도 꾸준히 낫다 — 풍향계처럼 여러 지표를 가중 평균하는 방식의 근거.",
                  url="https://econpapers.repec.org/RePEc:oup:rfinst:v:23:y:2010:i:2:p:821-862"),
    "hjtz_2015": D(cite="Huang, Jiang, Tu & Zhou (2015), Investor Sentiment Aligned: A Powerful Predictor of Stock Returns, Review of Financial Studies 28(3)",
                   finding="여러 심리 지표에서 공통 잡음을 걷어낸 심리 지수가 기존 심리 지수보다 훨씬 잘 예측한다(심리 지표를 여러 개 섞는 근거).",
                   url="https://econpapers.repec.org/RePEc:oup:rfinst:v:28:y:2015:i:3:p:791-837."),
}

FR = lambda i: {"src": "fred", "id": i}  # noqa: E731  (mix 안의 다리)
FT = lambda i: {"type": "fred", "id": i}  # noqa: E731  (FRED 시리즈 하나)
NV = lambda c: {"src": "naver", "fut": c}  # noqa: E731


def cand(name, short, group, cat, source, transform, direction, lag, stale, unit, dec, freq, why, papers_, chg=None, note=None):
    d = {"name": name, "short": short, "group": group, "cat": cat, "source": source, "transform": transform,
         "direction": direction, "lag_days": lag, "stale_days": stale, "unit": unit, "dec": dec, "freq": freq, "why": why}
    if chg:
        d["chg_days"] = chg
    return {"def": d, "papers": papers_, "status": "후보", **({"note": note} if note else {})}


MIX = lambda a, b=None: {"type": "mix", "num": a, **({"den": b} if b else {})}  # noqa: E731
EBP = {"src": "csv", "url": "https://www.federalreserve.gov/econres/notes/feds-notes/ebp_csv.csv", "col": "ebp", "name": "연준 EBP"}

C = {
    # ---------------- 원자재 비율 (선생님 지시: 금/은 비율 등 원자재가 들어간 비율)
    "gsr": cand("금/은 비율", "금/은", "tc", None, MIX(NV("GCcv1"), NV("SIcv1")), "level", -1, 1, 7, "배", 1, "매일",
                "금이 은보다 비싸질수록(비율↑) 위험 회피가 크다는 뜻. 역발상으로 비율이 높을수록 과열 점수가 낮음.", ["gsr_tail_2022", "gold_ratios_cep"]),
    "gsr_q": cand("금/은 비율 3개월 변화", "금/은Δ", "tc", None, MIX(NV("GCcv1"), NV("SIcv1")), "pct", -1, 1, 7, "%", 1, "매일",
                  "금/은 비율이 3개월 사이 빠르게 오르면 위험 회피가 커지는 중. 오를수록 과열 점수가 낮음.", ["gsr_tail_2022"], chg=91),
    "gpr": cand("금/백금 비율", "금/백금", "tc", None, MIX(NV("GCcv1"), NV("PLcv1")), "level", -1, 1, 7, "배", 2, "매일",
                "금/백금 비율이 높을수록 이후 주식 수익률이 높았다(Huang·Kilic 2019). 높을수록 과열 점수가 낮음(매수 쪽).", ["huang_kilic_2019", "pham_rudolf_2021"]),
    "gpr_y": cand("금/백금 비율 12개월 변화", "금/백금Δ", "tc", None, MIX(NV("GCcv1"), NV("PLcv1")), "pct", -1, 1, 7, "%", 1, "매일",
                  "비율의 변화가 수준보다 더 잘 맞았다(Xu 외 2023), 12개월 변화 상위 4분의 1 뒤 1년 수익률이 가장 높았다(Hulbert).",
                  ["xu_li_singh_2023", "hulbert_gp", "huang_kilic_2019"], chg=365),
    "cgr": cand("구리/금 비율", "구리/금", "lq", "E", MIX(NV("HGcv1"), NV("GCcv1")), "level", 1, 1, 7, "", 5, "매일",
                "경기(구리)와 안전자산(금)의 상대 가격. 높을수록 경기 기대가 크다는 통념 — 주식에는 반대였다는 점검도 있어 시험으로 확인.",
                ["copper_gold_2024", "sentimentrader_cg", "gold_ratios_cep"]),
    "cgr_q": cand("구리/금 비율 3개월 변화", "구리/금Δ", "lq", "E", MIX(NV("HGcv1"), NV("GCcv1")), "pct", 1, 1, 7, "%", 1, "매일",
                  "구리가 금보다 빠르게 오르면 경기 기대가 커지는 중.", ["copper_gold_2024"], chg=91),
    "gor": cand("금/유가 비율", "금/유가", "tc", None, MIX(NV("GCcv1"), FR("DCOILWTICO")), "level", -1, 1, 7, "배", 1, "매일",
                "금/유가 비율이 높을수록 이후 주식 수익률이 높았다(Yang 2024). 높을수록 과열 점수가 낮음.", ["yang_2024", "gold_ratios_cep"]),
    "cu_q": cand("구리 3개월 변화", "구리", "lq", "E", MIX(NV("HGcv1")), "pct", -1, 1, 7, "%", 1, "매일",
                 "경기 확장기에 산업금속이 오르면 이후 주식에 나빴다(Jacobsen 외 2019). 오를수록 낮은 점수.", ["jacobsen_2019", "hong_2007"], chg=91),
    "gold_q": cand("금 3개월 변화", "금", "tc", None, MIX(NV("GCcv1")), "pct", -1, 1, 7, "%", 1, "매일",
                   "금이 빠르게 오르면 안전자산 쏠림(두려움). 오를수록 과열 점수가 낮음 — 근거가 엇갈려 시험용.", ["yang_2024", "gold_ratios_cep"], chg=91),
    # ---------------- 변동성
    "vrp": cand("변동성 위험 프리미엄", "VRP", "tc", None, {"type": "calc", "name": "vrp"}, "level", -1, 1, 7, "%²", 0, "매일",
                "VIX² − 최근 22거래일 실현 분산. 높을수록(두려움에 보험료를 많이 낼수록) 이후 분기 수익률이 높았다. 높을수록 과열 점수가 낮음.", ["btz_2009"],
                note="논문은 장중 자료로 실현 분산을 쟀고 여기서는 일별 종가로 잰다(예측력이 약해질 수 있음)."),
    "gvz": cand("금 변동성 지수(GVZ)", "GVZ", "tc", None, FT("GVZCLS"), "level", -1, 1, 7, "", 1, "매일",
                "금 옵션의 공포 지수. 높을수록 두려움이 크다 → 과열 점수가 낮음. 시험용.", []),
    "ovx": cand("원유 변동성 지수(OVX)", "OVX", "tc", None, FT("OVXCLS"), "level", -1, 1, 7, "", 1, "매일",
                "원유 옵션의 공포 지수. 높을수록 과열 점수가 낮음. 시험용.", []),
    # ---------------- 경기·신용 (FRED, 정확한 공표치)
    "nos": cand("내구재 신규주문/출하 비율", "주문/출하", "lq", "E", {"type": "fred_ratio", "num": "DGORDER", "den": "AMDMVS"}, "level", -1, 58, 100, "배", 3, "매월",
                "주문이 출하보다 많이 쌓이면(비율↑) 경기 정점 근처라 이후 주식 수익률이 낮았다(Jones·Tuzel 2013). 높을수록 낮은 점수.", ["jones_tuzel_2013"]),
    "ebp": cand("초과 채권 프리미엄(EBP)", "EBP", "lq", "B", MIX(EBP), "level", -1, 60, 100, "%p", 2, "매월",
                "회사채 시장의 위험 회피 정도(연준 계산). 높을수록 돈 빌리기 어렵고 경기 침체 위험이 크다 → 낮은 점수.", ["gz_ebp"]),
    "t10y3m": cand("장단기 금리차(10년−3개월)", "10y−3m", "lq", "B", FT("T10Y3M"), "level", 1, 1, 7, "%p", 2, "매일",
                   "금리차가 클수록(곡선이 가팔라질수록) 경기 기대가 좋다. 이미 관찰 중인 10년−2년과 비교용.", []),
    "baa10y": cand("Baa 회사채 − 10년물 금리차", "Baa−10y", "lq", "B", FT("BAA10Y"), "level", -1, 1, 7, "%p", 2, "매일",
                   "Goyal·Welch가 쓰는 '부도 스프레드' 계열. 넓을수록 신용이 빡빡 → 낮은 점수.", ["gwz_2024"]),
    "tbill_y": cand("3개월 국채금리 12개월 변화", "단기금리Δ", "lq", "B", FT("TB3MS"), "chg", -1, 35, 70, "%p", 2, "매월",
                    "단기 금리가 1년 사이 많이 오르면 돈이 비싸진다 → 낮은 점수(Campbell 1987 계열).", ["gwz_2024"], chg=365),
    "sahm": cand("삼 법칙 실업 지표(실시간)", "삼 법칙", "lq", "E", FT("SAHMREALTIME"), "level", -1, 40, 75, "%p", 2, "매월",
                 "실업률 3개월 평균이 지난 1년 최저보다 얼마나 올랐나. 0.5 넘으면 경기 침체 신호 → 높을수록 낮은 점수.", []),
    "sloos": cand("은행 대출 기준 강화 비율(SLOOS)", "대출 기준", "lq", "C", FT("DRTSCILM"), "level", -1, 40, 130, "%", 1, "분기",
                  "대기업 대출 기준을 강화한 은행 비율(연준 설문). 높을수록 돈줄이 막힘 → 낮은 점수.", []),
    "ccsa_h": cand("계속 실업수당 청구 6개월 변화", "계속청구", "lq", "E", FT("CCSA"), "pct", -1, 12, 21, "%", 1, "매주",
                   "실업수당을 계속 받는 사람이 늘수록 고용이 식는 중 → 낮은 점수.", [], chg=182),
}

requests_ = [
    {"key": "short_interest", "name": "시장 전체 공매도 잔고", "papers": ["rrz_2016"],
     "why": "논문상 가장 강한 예측 변수 중 하나지만, 시장 전체를 합친 정확한 공개 수치(무료·정기)를 아직 못 찾음. 거래소 종목별 공매도 잔고를 합치는 방법을 확인해야 함."},
    {"key": "bdi", "name": "발틱 건화물 운임지수(BDI)", "papers": ["bakshi_2011"],
     "why": "3개월 증가율이 1~3개월 세계 주식을 예측. 발틱 거래소 자료는 유료라 정확한 일별 공개 출처가 필요."},
    {"key": "output_gap", "name": "산출 갭(산업생산 추세 대비)", "papers": ["cooper_priestley_2009"],
     "why": "FRED 산업생산(INDPRO)으로 계산 가능하지만 '그때까지의 자료로만' 추세를 맞추는 계산(실시간 2차 추세)을 도구에 넣어야 함."},
    {"key": "kr_export", "name": "한국 수출 증가율(관세청)", "papers": [],
     "why": "11-21 위원회 자료 요청(5표). 코스피와 직접 이어지는 경기 자료. 공식 출처의 정기 자료 받기 방법 필요."},
]

lib = {
    "_안내": ("팩터 도서관 — 증시 방향(사기/기다리기/줄이기)을 미리 맞히는 데 쓸 수 있는 신호 후보와 근거 논문을 모아 두는 곳. "
              "선생님 지시(2026-11-21): 금/은 비율 같은 원자재 비율 등 수치로 정확히 얻을 수 있는 것을 후보로 두고, 고정하지 말고 다양하게 시도하며, "
              "논문을 찾아 좋은 팩터를 기억했다가 수치로 시험해 팩터 변경·가중치 조정에 반영. "
              "시험은 scripts/factor_lab.py, 등록·넣기·빼기는 위원회(WEIGHTS.md 8절), 기존 지표 가중치는 결정 모델."),
    "updated": "2026-11-21",
    "status_words": {"후보": "도서관에만 있음(시험만)", "관찰": "data/factors.json에 watch로 등록", "사용": "active", "보류": "시험 결과가 약하거나 반대", "자료 요청": "정확한 출처가 아직 없음"},
    "rules": [
        "숫자는 공식 통계·거래소 종가처럼 정확한 값만. 추정치·스크래핑 요약값은 쓰지 않는다.",
        "공개 지연(lag_days)을 꼭 넣어 그날 알 수 있던 값만 쓴다(미리 보기 금지).",
        "후보를 많이 시험할수록 우연히 좋아 보이는 것이 생긴다(25개를 시험하면 1~2개는 우연). 장기(2010~)·앞뒤 절반·최근 3년이 모두 같은 방향인 것만 믿는다.",
        "논문 결과는 발표 뒤 약해지는 일이 많다(McLean·Pontiff 2016, Goyal·Welch·Zafirov 2024) — 최근 자료로 다시 확인한다.",
        "방향(direction)은 논문·경제 논리로 먼저 정하고 시험 결과를 보고 뒤집지 않는다. 반대로 나오면 '보류'로 두고 위원회가 따로 판단한다.",
        "한 신호에 기대지 않고 여러 신호를 작은 가중치로 섞는다(Rapach·Strauss·Zhou 2010).",
    ],
    "papers": papers,
    "candidates": C,
    "requests": requests_,
}

if __name__ == "__main__":
    if os.path.exists(OUT):
        raise SystemExit("data/factor_library.json이 이미 있습니다. 직접 고치세요.")
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(lib, f, ensure_ascii=False, indent=1)
    print(OUT, len(C), "후보,", len(papers), "논문")
