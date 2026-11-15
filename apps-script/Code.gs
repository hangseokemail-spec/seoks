/**
 * Seoks → Google 시트 기록 + 구독자 메일
 * 사용법: 시트에서 [확장 프로그램 > Apps Script] → 이 코드를 붙여넣고 저장 → setup 함수를 한 번 실행(권한 승인).
 * 이후 매일 아침 7시쯤 자동으로 기록하고, '구독자' 탭에 Y로 표시한 사람에게 요약 메일을 보냅니다.
 */
const BASE = 'https://hangseokemail-spec.github.io/seoks/';

function setup() {
  const ss = SpreadsheetApp.getActive();
  if (!ss.getSheetByName('일별기록')) ss.getSheets()[0].setName('일별기록');
  ['현황판', '구독자'].forEach(function (n) { if (!ss.getSheetByName(n)) ss.insertSheet(n); });
  const sub = ss.getSheetByName('구독자');
  if (sub.getLastRow() === 0) sub.appendRow(['이메일', '이름', '메일 받기(Y/N)']);
  ScriptApp.getProjectTriggers().forEach(function (t) { ScriptApp.deleteTrigger(t); });
  ScriptApp.newTrigger('daily').timeBased().everyDays(1).atHour(7).nearMinute(0).inTimezone('Asia/Seoul').create();
  daily();
}

function getJSON_(path) {
  const r = UrlFetchApp.fetch(BASE + path + '?t=' + Date.now(), { muteHttpExceptions: true });
  if (r.getResponseCode() !== 200) return null;
  return JSON.parse(r.getContentText());
}

function daily() {
  const latest = getJSON_('data/latest.json');
  const series = getJSON_('data/series.json');
  if (!latest || !series) throw new Error('Seoks 데이터를 불러오지 못했습니다');
  writeSeries_(series);
  const d = latest.date;
  const board = latest.boards.indexOf(d) >= 0 ? getJSON_('data/board/' + d + '.json') : null;
  const cm = getJSON_('data/comments/' + d + '.json');
  if (board) writeBoard_(board, cm);
  sendMail_(d, series, board, cm);
}

function labelTC_(x) { return x == null ? '' : x >= 4.5 ? '광기' : x >= 3.5 ? '과열' : x >= 2.5 ? '중립' : x >= 1.5 ? '불안' : '공포'; }
function labelLQ_(x) { return x == null ? '' : x >= 4.5 ? '풍부' : x >= 3.5 ? '우호' : x >= 2.5 ? '중립' : x >= 1.5 ? '긴축' : '경색'; }

const COLS = [['spx','S&P500'],['ixic','나스닥종합'],['dji','다우'],['ndx','나스닥100'],['kospi','코스피'],['vix','VIX'],['dxy','달러인덱스'],['us10y','미10년물'],
  ['tc','트렌드캐치'],['#tc','트렌드캐치 판단'],['tc_n','트렌드캐치 지표수'],['lq','유동성'],['#lq','유동성 판단'],
  ['tc_fg','F&G'],['s_tc_fg','F&G 점수'],['tc_aaii','AAII 스프레드'],['s_tc_aaii','AAII 점수'],['tc_vix','VIX 값'],['s_tc_vix','VIX 점수'],
  ['tc_hy','하이일드%'],['s_tc_hy','하이일드 점수'],['tc_pc','풋콜'],['s_tc_pc','풋콜 점수'],['tc_margin','신용융자 YoY%'],['s_tc_margin','신용융자 점수'],
  ['tc_a200','S&P500 200일선 위%'],['s_tc_a200','200일선 점수'],['tc_rsi','RSI14'],['s_tc_rsi','RSI 점수'],['tc_dev','200일 이격도%'],['s_tc_dev','이격도 점수'],
  ['lq_fed','연준자산 3M%'],['s_lq_fed','연준자산 점수'],['lq_nl','순유동성 3M%'],['s_lq_nl','순유동성 점수'],['lq_m2','M2 YoY%'],['s_lq_m2','M2 점수'],
  ['lq_effr','EFFR 3M %p'],['s_lq_effr','EFFR 점수'],['lq_dxy','DXY 6M%'],['s_lq_dxy','DXY 점수'],['lq_bank','은행신용 YoY%'],['s_lq_bank','은행신용 점수'],
  ['lq_vol','거래량 20일대비%'],['s_lq_vol','거래량 점수'],['lq_nfci','NFCI'],['s_lq_nfci','NFCI 점수'],['lq_y10_chg','10년물 13주 변화bp'],['s_lq_y10','10년물 점수']];

function writeSeries_(s) {
  const sh = SpreadsheetApp.getActive().getSheetByName('일별기록');
  const head = ['날짜'].concat(COLS.map(function (c) { return c[1]; }));
  const rows = s.dates.map(function (d, i) {
    return [d].concat(COLS.map(function (c) {
      if (c[0] === '#tc') return labelTC_(s.cols.tc[i]);
      if (c[0] === '#lq') return labelLQ_(s.cols.lq[i]);
      const a = s.cols[c[0]]; const v = a ? a[i] : null; return v == null ? '' : v;
    }));
  }).reverse();
  sh.clearContents();
  sh.getRange(1, 1, 1, head.length).setValues([head]).setFontWeight('bold');
  sh.getRange(2, 1, rows.length, head.length).setValues(rows);
  sh.setFrozenRows(1);
}

function writeBoard_(b, cm) {
  const sh = SpreadsheetApp.getActive().getSheetByName('현황판');
  if (sh.getLastRow() === 0) sh.appendRow(['날짜', '상승', '하락', '신고가', '신저가', '50일선 위%', '200일선 위%', 'S&P500 200일선 위%', '트렌드캐치', '유동성', '대표 신고가', '한 줄 해석']);
  const dates = sh.getLastRow() > 1 ? sh.getRange(2, 1, sh.getLastRow() - 1, 1).getDisplayValues().map(function (r) { return r[0]; }) : [];
  if (dates.indexOf(b.date) >= 0) return;
  const br = b.breadth;
  sh.insertRowAfter(1);
  sh.getRange(2, 1, 1, 12).setValues([[b.date, br.adv, br.dec, br.nh, br.nl, br.above50, br.above200, br.sp500_above200,
    b.tc, b.lq, b.features.map(function (f) { return f.t; }).join(', '), cm && cm.oneliner ? cm.oneliner : '']]);
}

function sendMail_(d, s, b, cm) {
  const props = PropertiesService.getScriptProperties();
  if (props.getProperty('lastMailed') === d) return;
  const sub = SpreadsheetApp.getActive().getSheetByName('구독자');
  if (sub.getLastRow() < 2) { props.setProperty('lastMailed', d); return; }
  const list = sub.getRange(2, 1, sub.getLastRow() - 1, 3).getValues()
    .filter(function (r) { return r[0] && String(r[2]).toUpperCase().indexOf('Y') === 0; }).map(function (r) { return r[0]; });
  if (!list.length) { props.setProperty('lastMailed', d); return; }
  const i = s.dates.indexOf(d), c = s.cols;
  const pct = function (k) { const a = c[k][i], p = c[k][i - 1]; return (a && p) ? ((a / p - 1) * 100).toFixed(2) + '%' : '—'; };
  const tc = c.tc[i], lq = c.lq[i];
  const subject = 'Seoks | ' + d.slice(5).replace('-', '/') + ' 마감 · 트렌드캐치 ' + tc + ' ' + labelTC_(tc) + ' · 유동성 ' + lq + ' ' + labelLQ_(lq);
  let html = '<div style="font-family:sans-serif;max-width:560px">'
    + '<h2 style="color:#c9a54a;margin:0">Seoks</h2><p style="margin:4px 0 12px">' + d + ' 미국 증시 마감</p>'
    + '<p>S&amp;P500 ' + pct('spx') + ' · 나스닥 ' + pct('ixic') + ' · 다우 ' + pct('dji') + '</p>';
  if (b) html += '<p>상승 ' + b.breadth.adv + ' / 하락 ' + b.breadth.dec + ' · 신고가 ' + b.breadth.nh + ' / 신저가 ' + b.breadth.nl + '</p>';
  html += '<p><b>트렌드캐치</b> ' + tc + ' ' + labelTC_(tc) + ' · <b>유동성</b> ' + lq + ' ' + labelLQ_(lq) + '</p>';
  if (cm && cm.oneliner) html += '<p style="border-left:3px solid #c9a54a;padding-left:8px"><b>' + cm.oneliner + '</b></p>';
  html += '<p><a href="' + BASE + '">현황판 열기</a></p><p style="color:#888;font-size:12px">참고 자료이며 투자 권유가 아닙니다.</p></div>';
  MailApp.sendEmail({ to: Session.getActiveUser().getEmail(), bcc: list.join(','), subject: subject, htmlBody: html });
  props.setProperty('lastMailed', d);
}
