/* Seoks 증시현황판 */
(() => {
  const M = window.META;
  const TCC = ["#3b82f6", "#8ab8f2", "#94a3b8", "#f59e6b", "#ef4444"];
  const LQC = ["#b45309", "#f2b84b", "#94a3b8", "#5fd3b0", "#0fb9a5"];
  const TC_Z = ["공포", "불안", "중립", "과열", "광기"];
  const LQ_Z = ["경색", "긴축", "중립", "우호", "풍부"];
  const SECTOR_COL = { "헬스케어": "#e0679b", "금융": "#4f8ef7", "기술": "#7dd3fc", "필수소비재": "#fbbf24", "산업재": "#6ee7a0",
    "유틸리티": "#a78bfa", "커뮤니케이션": "#c084fc", "부동산": "#cbd5e1", "경기소비재": "#fb923c", "소재": "#a3e635", "에너지": "#f87171" };
  const SIGNED = new Set(["aaii", "margin", "dev", "fed", "nl", "m2", "effr", "dxy", "bank"]);
  const IDX_NAME = { ndx: "나스닥100", spx: "S&P500", kospi: "코스피" };

  const S = { tab: "board", date: null, idx: "ndx", h: "4", range: "3y", calOpen: false, calMonth: null, aidx: "spx", analysis: null, notes: {},
    series: null, corr: null, latest: null, boards: {}, comments: {} };
  const charts = {};
  const $ = (s, el = document) => el.querySelector(s);
  const esc = (t) => String(t ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

  // ---------------------------------------------------------------- 공통 함수
  const labelTC = (x) => x == null ? null : x >= 4.5 ? "광기" : x >= 3.5 ? "과열" : x >= 2.5 ? "중립" : x >= 1.5 ? "불안" : "공포";
  const labelLQ = (x) => x == null ? null : x >= 4.5 ? "풍부" : x >= 3.5 ? "우호" : x >= 2.5 ? "중립" : x >= 1.5 ? "긴축" : "경색";
  const colTC = (lab) => TCC[TC_Z.indexOf(lab)] || "#475569";
  const colLQ = (lab) => LQC[LQ_Z.indexOf(lab)] || "#475569";
  const pill = (lab, col) => lab ? `<span class="pill" style="background:${col}">${lab}</span>` : `<span class="pill" style="background:#334155;color:#cbd5e1">자료 없음</span>`;
  const n2 = (v, d = 2) => v == null || isNaN(v) ? "—" : Number(v).toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d });
  const sgn = (v, d = 2, u = "") => v == null || isNaN(v) ? "—" : (v > 0 ? "+" : v < 0 ? "−" : "") + n2(Math.abs(v), d) + u;
  const cls = (v) => v == null ? "flat" : v > 0 ? "up" : v < 0 ? "down" : "flat";
  const fmtDateKo = (d) => { const [y, m, dd] = d.split("-").map(Number); return `${m}월 ${dd}일`; };
  const dow = (d) => "일월화수목금토"[new Date(d + "T00:00:00").getDay()];
  const short = (d) => { const [, m, dd] = d.split("-"); return `${+m}/${+dd}`; };

  async function getJSON(url) {
    const r = await fetch(url + (url.includes("?") ? "&" : "?") + "v=" + encodeURIComponent(S.latest ? S.latest.generated : Date.now()));
    if (!r.ok) throw new Error(url + " " + r.status);
    return r.json();
  }
  const D = () => S.series.dates;
  const C = (k) => S.series.cols[k] || [];
  const at = (k, i) => (i < 0 || i == null) ? null : (C(k)[i] ?? null);
  function idxOf(date) {
    const ds = D(); let lo = 0, hi = ds.length - 1, ans = -1;
    while (lo <= hi) { const m = (lo + hi) >> 1; if (ds[m] <= date) { ans = m; lo = m + 1; } else hi = m - 1; }
    return ans;
  }
  function weekEnds(i, count) { // i 이하의 주 마지막 거래일 인덱스 count개 (마지막은 i 자신)
    const ds = D(), out = [i]; let k = i - 1;
    const wk = (d) => { const t = new Date(d + "T00:00:00"); const day = (t.getDay() + 6) % 7; t.setDate(t.getDate() - day); return t.toISOString().slice(0, 10); };
    let cur = wk(ds[i]);
    while (k >= 0 && out.length < count) {
      if (wk(ds[k]) !== cur) { out.push(k); cur = wk(ds[k]); }
      k--;
    }
    return out.reverse();
  }
  async function board(date) {
    if (!S.latest.boards.includes(date)) return null;
    if (!(date in S.boards)) { try { S.boards[date] = await getJSON(`data/board/${date}.json`); } catch (e) { S.boards[date] = null; } }
    return S.boards[date];
  }
  async function comments(date) {
    if (!(date in S.comments)) { try { S.comments[date] = await getJSON(`data/comments/${date}.json`); } catch (e) { S.comments[date] = null; } }
    return S.comments[date];
  }
  function killChart(id) { if (charts[id]) { charts[id].destroy(); delete charts[id]; } }

  // ---------------------------------------------------------------- 상태·URL
  function readURL() {
    const p = new URLSearchParams(location.search);
    if (["board", "tc", "lq"].includes(p.get("tab"))) S.tab = p.get("tab");
    if (p.get("date")) S.date = p.get("date");
  }
  function writeURL() {
    const p = new URLSearchParams(); p.set("tab", S.tab); if (S.date !== S.latest.date) p.set("date", S.date);
    history.replaceState(null, "", "?" + p.toString());
  }
  function setDate(d) { S.date = d; S.calOpen = false; render(); }
  function step(n) { const i = idxOf(S.date) + n; if (i >= 0 && i < D().length) setDate(D()[i]); }

  // ---------------------------------------------------------------- 날짜 바·달력
  function dotColor(i) {
    if (S.tab === "lq") { const l = labelLQ(at("lq", i)); return l ? colLQ(l) : "#334155"; }
    const l = labelTC(at("tc", i)); return l ? colTC(l) : "#334155";
  }
  function renderDatebar() {
    const ds = D(), i = idxOf(S.date), last = ds.length - 1;
    let e = last - i <= 4 ? last : i; const s = Math.max(0, e - 4);
    const chips = [];
    for (let k = s; k <= e; k++) {
      const d = ds[k], bd = S.latest.boards.includes(d);
      chips.push(`<button class="chip ${k === i ? "on" : ""}" data-d="${d}" title="${d}${bd ? " · 현황판 있음" : ""}"><span class="dot" style="background:${dotColor(k)}"></span>${short(d)} ${dow(d)}</button>`);
    }
    $("#datebar").innerHTML =
      `<button class="chip nav" id="prev" ${i <= 0 ? "disabled" : ""} aria-label="이전 거래일">‹</button>${chips.join("")}
       <button class="chip nav" id="next" ${i >= last ? "disabled" : ""} aria-label="다음 거래일">›</button>
       <button class="chip" id="calbtn">달력</button>
       ${i !== last ? `<button class="chip" id="today">최신</button>` : ""}
       <span class="sp"></span><span class="muted" style="font-size:12px">점 색 = ${S.tab === "lq" ? "유동성" : "트랜드캐치"} 판단</span>
       ${S.calOpen ? renderCal() : ""}`;
    $("#datebar").querySelectorAll("[data-d]").forEach((b) => b.onclick = () => setDate(b.dataset.d));
    $("#prev").onclick = () => step(-1); $("#next").onclick = () => step(1);
    $("#calbtn").onclick = () => { S.calOpen = !S.calOpen; S.calMonth = S.date.slice(0, 7); renderDatebar(); };
    if ($("#today")) $("#today").onclick = () => setDate(ds[last]);
    if (S.calOpen) {
      $("#cprev").onclick = () => { S.calMonth = addMonth(S.calMonth, -1); renderDatebar(); };
      $("#cnext").onclick = () => { S.calMonth = addMonth(S.calMonth, 1); renderDatebar(); };
      $(".cal").querySelectorAll(".d.has").forEach((b) => b.onclick = () => setDate(b.dataset.d));
    }
  }
  function addMonth(ym, n) { let [y, m] = ym.split("-").map(Number); m += n; while (m > 12) { m -= 12; y++; } while (m < 1) { m += 12; y--; } return `${y}-${String(m).padStart(2, "0")}`; }
  function renderCal() {
    const [y, m] = S.calMonth.split("-").map(Number);
    const first = new Date(y, m - 1, 1), days = new Date(y, m, 0).getDate();
    const set = new Map(); D().forEach((d, k) => { if (d.startsWith(S.calMonth)) set.set(d, k); });
    let cells = "일월화수목금토".split("").map((c) => `<div class="dow">${c}</div>`).join("");
    for (let k = 0; k < first.getDay(); k++) cells += "<div></div>";
    for (let dd = 1; dd <= days; dd++) {
      const d = `${S.calMonth}-${String(dd).padStart(2, "0")}`, k = set.get(d);
      if (k == null) { cells += `<div class="d">${dd}</div>`; continue; }
      cells += `<div class="d has ${d === S.date ? "sel" : ""} ${S.latest.boards.includes(d) ? "bd" : ""}" data-d="${d}">${dd}<span class="dd" style="background:${dotColor(k)}"></span></div>`;
    }
    const minM = D()[0].slice(0, 7), maxM = D()[D().length - 1].slice(0, 7);
    return `<div class="cal"><div class="ch"><button id="cprev" ${S.calMonth <= minM ? "disabled" : ""}>‹</button><span>${y}년 ${m}월</span><button id="cnext" ${S.calMonth >= maxM ? "disabled" : ""}>›</button></div>
      <div class="grid">${cells}</div><div class="lg">점: 그날 ${S.tab === "lq" ? "유동성" : "트랜드캐치"} 판단 색 · 금색 테두리: 현황판 기록이 있는 날</div></div>`;
  }

  // ---------------------------------------------------------------- 공통 위젯
  function spark(arr, up) {
    const v = (arr || []).filter((x) => x != null); if (v.length < 2) return "";
    const mn = Math.min(...v), mx = Math.max(...v), w = 100, h = 30;
    const pts = v.map((x, k) => `${(k / (v.length - 1)) * w},${h - 3 - ((x - mn) / (mx - mn || 1)) * (h - 6)}`).join(" ");
    return `<svg class="spark" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none"><polyline points="${pts}" fill="none" stroke="${up ? "#34d399" : "#ff6b7a"}" stroke-width="1.6" vector-effect="non-scaling-stroke"/></svg>`;
  }
  function seriesIdx(k, i, dec = 2) {
    const a = C(k); let j = i; while (j >= 0 && a[j] == null) j--; let p = j - 1; while (p >= 0 && a[p] == null) p--;
    if (j < 0 || p < 0) return null;
    return { close: a[j], chg: (a[j] / a[p] - 1) * 100, spark: a.slice(Math.max(0, j - 5), j + 1) };
  }

  // ---------------------------------------------------------------- 증시현황판
  function dayChart(x, baseOverride) {
    if (!x || !x.pts || x.pts.length < 2) return "";
    const v = x.pts, base = baseOverride ?? x.prev ?? v[0];
    const all = v.concat([base]), mn = Math.min(...all), mx = Math.max(...all), w = 100, h = 34;
    const Y = (y) => h - 3 - ((y - mn) / (mx - mn || 1)) * (h - 6);
    const pts = v.map((y, k) => `${(k / (v.length - 1)) * w},${Y(y)}`).join(" ");
    const col = v[v.length - 1] >= base ? "#3ee0a1" : "#ff7b8a";
    return `<svg class="spark" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none"><line x1="0" x2="${w}" y1="${Y(base)}" y2="${Y(base)}" stroke="#98acd0" stroke-width="1" stroke-dasharray="3 3" vector-effect="non-scaling-stroke"/><polyline points="${pts}" fill="none" stroke="${col}" stroke-width="1.8" vector-effect="non-scaling-stroke"/></svg>`;
  }
  const descOf = (r) => r.desc || (S.notes[r.t] && S.notes[r.t].desc) || `${r.name}${r.ind ? " · " + r.ind : ""}`;
  async function viewBoard() {
    const i = idxOf(S.date), d = D()[i];
    const b = await board(d), cm = (await comments(d)) || {};
    const ind = b ? b.indices : {
      spx: seriesIdx("spx", i), ixic: seriesIdx("ixic", i), dji: seriesIdx("dji", i), ndx: seriesIdx("ndx", i),
      kospi: seriesIdx("kospi", i), vix: seriesIdx("vix", i), dxy: seriesIdx("dxy", i, 3),
      us10y: (() => { const a = C("us10y"); return a[i] == null ? null : { close: a[i], chg_bp: a[i - 1] != null ? (a[i] - a[i - 1]) * 100 : null, spark: a.slice(Math.max(0, i - 5), i + 1) }; })(),
    };
    const ID = (b && b.intraday) || {};
    const chartFor = (k, x, up) => {
      const src = { spx: "spx", ixic: "ndx", dji: "dji", ndx: "ndx", kospi: "kospi" }[k];
      const it = src && ID[src];
      if (it) {
        const prevIdx = (() => { const a = C(k); let j = i - 1; while (j >= 0 && a[j] == null) j--; return j >= 0 ? a[j] : null; })();
        if (k === "kospi") return dayChart(it, prevIdx) + `<div class="cl2">장중 흐름 · 네이버 분봉</div>`;
        if (prevIdx && it.prev) {  // ETF 흐름을 지수 전일 종가 기준으로 환산
          const sc = { pts: it.pts.map((p) => prevIdx * p / it.prev), prev: prevIdx };
          return dayChart(sc) + `<div class="cl2">장중 흐름 · finviz ${it.src} 5분봉으로 환산</div>`;
        }
        return dayChart(it) + `<div class="cl2">장중 흐름 · finviz ${it.src}</div>`;
      }
      return spark(x.spark, up) + `<div class="cl2">최근 6거래일</div>`;
    };
    const big = [["spx", "S&P 500"], ["ixic", "Nasdaq"], ["dji", "Dow"]].map(([k, nm]) => {
      const x = ind[k]; if (!x) return `<div class="card">${nm} —</div>`;
      return `<div class="card click" data-info="board:index"><div class="idx"><span class="nm">${nm}</span><span class="pct num ${cls(x.chg)}">${sgn(x.chg, 2, "%")}</span></div>
        <div class="cl num">${n2(x.close, 2)}</div>${chartFor(k, x, x.chg >= 0)}</div>`;
    }).join("");
    const minis = [["ndx", "나스닥100", 2], ["kospi", "코스피", 2], ["vix", "VIX", 2], ["dxy", "달러인덱스", 2]].map(([k, nm, dd]) => {
      const x = ind[k]; if (!x) return `<div class="card mini">${nm} —</div>`;
      const c = cls(k === "vix" ? -x.chg : x.chg);
      return `<div class="card mini click" data-info="board:index"><span class="nm">${nm}</span><span class="v num">${n2(x.close, dd)} <small class="${c}">${sgn(x.chg, 2, "%")}</small></span>${chartFor(k, x, k === "vix" ? x.chg <= 0 : x.chg >= 0)}</div>`;
    }).join("") + (() => { const y = ind.us10y; if (!y) return `<div class="card mini">미 10년물 —</div>`;
      return `<div class="card mini click" data-info="board:index"><span class="nm">미 10년물 (전일 기준)</span><span class="v num">${n2(y.close, 2)}% <small class="${cls(-(y.chg_bp))}">${y.chg_bp != null ? sgn(y.chg_bp, 0, "bp") : ""}</small></span>${spark(y.spark, (y.chg_bp || 0) <= 0)}<div class="cl2">최근 6거래일</div></div>`; })();

    let html = `<div class="grid g3">${big}</div><div class="grid g5 sec">${minis}</div>`;
    if (!b) {
      html += `<div class="empty sec">${S.latest.boards.length ? `현황판(Breadth·섹터·신고가·특징주) 기록은 ${S.latest.boards[0]}부터 쌓이고 있습니다.` : "아직 현황판 기록이 없습니다."}<br>
        이 날짜의 트랜드캐치·유동성은 위 탭에서 볼 수 있습니다.</div>`;
      $("#view").innerHTML = html; bindInfo(); return;
    }
    // 시장의 변화
    const mk = cm.market || {};
    const sp = b.sector_perf || [], gn = b.gainers || [];
    const autoLead = sp.length ? `강한 섹터 ${sp.slice(0, 2).map((s) => `${s.name} ${sgn(s.chg, 2, "%")}`).join(", ")} · 약한 섹터 ${sp.slice(-1).map((s) => `${s.name} ${sgn(s.chg, 2, "%")}`).join("")} · 강세주 ${gn.slice(0, 3).map((g) => `${g.t} ${sgn(g.chg, 1, "%")}`).join(", ")}` : "";
    const tcv = at("tc", i), lqv = at("lq", i);
    html += `<div class="oneliner market"><span class="lb">시장의 변화</span><span class="tx">${esc(mk.headline || cm.oneliner || "코멘트 준비 중입니다")}</span>
      ${(mk.news || []).length ? `<ul class="news">${mk.news.map((n) => `<li>${esc(n)}</li>`).join("")}</ul>` : ""}
      <div class="lead"><b>주도 섹터·강한 기업</b>${esc(mk.leaders || autoLead)}</div>
      <div class="scorechips"><button class="chip" data-go="tc">트랜드캐치 ${tcv ?? "—"} ${pill(labelTC(tcv), colTC(labelTC(tcv)))}</button>
      <button class="chip" data-go="lq">유동성 ${lqv ?? "—"} ${pill(labelLQ(lqv), colLQ(labelLQ(lqv)))}</button></div></div>`;
    // Breadth + 섹터 강도
    const br = b.breadth, pv = b.prev;
    const rows = [["adv", "상승 종목", 0, 1], ["dec", "하락 종목", 0, -1], ["nh", "신규 신고가", 0, 1], ["nl", "신규 신저가", 0, -1],
      ["above50", "50일선 위", 1, 1], ["above200", "200일선 위", 1, 1], ["sp500_above200", "S&P500 200일선 위", 1, 1]];
    const trs = rows.map(([k, nm, pct, good]) => {
      const now = br[k], was = pv ? pv[k] : null, ch = was == null ? null : now - was;
      const fmt = (v) => v == null ? "—" : pct ? n2(v, 1) + "%" : Number(v).toLocaleString();
      const chs = ch == null ? "—" : (pct ? sgn(ch, 1, "%p") : (ch > 0 ? "+" : ch < 0 ? "−" : "") + Math.abs(ch).toLocaleString());
      return `<tr class="click" data-info="board:${k}"><td>${nm}</td><td class="num">${fmt(was)}</td><td class="num now">${fmt(now)}</td><td class="num ${ch == null ? "flat" : ch * good > 0 ? "up" : ch * good < 0 ? "down" : "flat"}">${chs}</td></tr>`;
    }).join("");
    html += `<div class="grid g2 sec">
      <div class="card"><h3>시장 Breadth</h3><div class="cap">${short(b.date)} 종가 · finviz 전체 ${br.universe.toLocaleString()}종목 (ETF 제외) · 항목을 누르면 설명</div>
        <table class="bt"><tr><th>항목</th><th>${pv ? short(pv.date) : "전일"}</th><th>${short(b.date)}</th><th>변화</th></tr>${trs}</table>
        ${pv ? "" : `<div class="note">전일 칸은 다음 거래일부터 채워집니다 (finviz는 과거 조회가 안 됨).</div>`}</div>
      <div class="card click" data-info="board:sectors"><h3>섹터 강도</h3><div class="cap">섹터별 시가총액 가중 등락률 · 괄호는 상승 종목 비율</div>
        <div class="chartbox" style="height:${Math.max(220, sp.length * 26)}px"><canvas id="secbar"></canvas></div></div></div>`;
    // 강세주 + 업종 분포
    const stRow = (r, n) => `<tr><td class="r muted">${n}</td><td class="t">${r.t}</td><td class="ds">${esc(descOf(r))}</td><td class="r ${cls(r.chg)} num">${sgn(r.chg, 2, "%")}</td></tr>`;
    const top = b.top40.length;
    const leg = b.sectors.map((s) => `<div class="row"><span class="sw" style="background:${SECTOR_COL[s.name] || "#64748b"}"></span>${esc(s.name)}<span class="ct num">${s.count}개 ${n2(s.pct, 1)}%</span></div>`).join("");
    html += `<div class="grid g2 sec">
      <div class="card click" data-info="board:gainers"><h3>강세주 · 약세주 (S&P500)</h3><div class="cap">S&P500 구성종목 당일 등락률 상위 10 · 하위 5</div>
        <table class="st">${gn.map((r, n) => stRow(r, n + 1)).join("")}</table>
        <div class="cap" style="margin:10px 0 2px">약세 5</div><table class="st">${(b.losers || []).map((r, n) => stRow(r, n + 1)).join("")}</table>
        <div class="cap" style="margin:10px 0 2px">시가총액 상위 10</div><div class="mchips">${(b.mega || []).map((r) => `<span><b>${r.t}</b> <span class="${cls(r.chg)}">${sgn(r.chg, 2, "%")}</span></span>`).join("")}</div>
        ${(b.ind_top || []).length ? `<div class="cap" style="margin:10px 0 2px">강한 산업 · 약한 산업 (시총 가중)</div><div class="mchips">${b.ind_top.slice(0, 3).map((x) => `<span>${esc(x.name)} <span class="up">${sgn(x.chg, 2, "%")}</span></span>`).join("")}${b.ind_bottom.slice(0, 3).map((x) => `<span>${esc(x.name)} <span class="down">${sgn(x.chg, 2, "%")}</span></span>`).join("")}</div>` : ""}</div>
      <div class="card click" data-info="board:top40"><h3>신고가 TOP${top} 업종 분포</h3><div class="cap">finviz 52주 신고가 ${b.nh_total}개 중 우선주·SPAC 제외, 시가총액 상위 ${top}개</div>
        <div class="donut"><div class="cv"><canvas id="donut"></canvas><div class="ctr"><b>${top}개</b><span>전체 100%</span></div></div><div class="legend">${leg}</div></div></div></div>`;
    // 대표 신고가 (S&P500)
    const F = cm.features || {};
    const cards = b.features.map((f) => {
      const c = F[f.t];
      const body = c ? `<div><div class="k">BM</div>${esc(c.bm)}</div><div class="hr"></div>
          <div><div class="k2">최근 실적·신고가 배경</div>${esc(c.e1)}<br><span class="sub">${esc(c.e2 || "")}</span></div><div class="hr"></div>
          <div class="pt"><b>포인트</b>${esc(c.point)}</div><div class="ct"><b>주의</b>${esc(c.caution)}</div>`
        : `<div class="pend">코멘트 준비 중</div><div class="sub">${esc(descOf(f))} · 시총 $${n2(f.mcap / 1000, 1)}B</div>`;
      return `<div class="fc"><div class="top"><span>${f.t}</span><span class="${cls(f.chg)} num">${sgn(f.chg, 2, "%")}</span></div><div class="bd">${body}</div></div>`;
    }).join("");
    html += `<div class="sec"><div style="display:flex;align-items:baseline;gap:10px;margin:6px 2px 8px"><h3 style="margin:0;color:var(--gold);font-size:18px">대표 신고가 ${b.features.length}선 (S&P500) · BM · 투자포인트</h3>
      <button class="muted click" data-info="board:features" style="font-size:12.5px">선정 기준</button></div>
      ${b.features.length ? `<div class="grid g4">${cards}</div>` : `<div class="empty">이날 S&P500 종목 중 52주 신고가가 없었습니다.</div>`}</div>`;
    // 신고가 TOP40 표
    const t40 = b.top40.map((r, n) => `<tr><td class="r muted">${n + 1}</td><td class="t">${r.t}${r.sp ? '<span class="badge-sp">S&P</span>' : ""}</td><td class="ds">${esc(descOf(r))}</td><td class="hs">${esc(r.sector)}</td><td class="r num hs2">$${r.mcap >= 1000 ? n2(r.mcap / 1000, 1) + "B" : n2(r.mcap, 0) + "M"}</td><td class="r ${cls(r.chg)} num">${sgn(r.chg, 2, "%")}</td></tr>`).join("");
    html += `<div class="card sec"><h3>신고가 TOP${top} 종목</h3><div class="cap">시가총액 순 · S&P = S&P500 구성종목 · 회사 설명은 Claude가 작성 (없으면 finviz 업종)</div>
      <table class="st"><tr><th class="r">#</th><th>티커</th><th>무슨 회사</th><th class="hs">섹터</th><th class="r hs2">시총</th><th class="r">등락</th></tr>${t40}</table></div>
      <div class="note">자료: finviz Elite (미국 ${short(b.date)} 정규장) · 네이버 증권 · 기업 공시·뉴스 / 실적은 당일 상승의 단일 원인으로 단정하지 않음 · 생성 ${esc(b.generated)}</div>`;
    $("#view").innerHTML = html;
    killChart("donut"); killChart("secbar");
    charts.donut = new Chart($("#donut"), { type: "doughnut",
      data: { labels: b.sectors.map((s) => s.name), datasets: [{ data: b.sectors.map((s) => s.count), backgroundColor: b.sectors.map((s) => SECTOR_COL[s.name] || "#64748b"), borderColor: "#243b69", borderWidth: 2 }] },
      options: { cutout: "58%", plugins: { legend: { display: false }, tooltip: { callbacks: { label: (c) => ` ${c.label} ${c.raw}개` } } }, maintainAspectRatio: false } });
    if (sp.length) charts.secbar = new Chart($("#secbar"), { type: "bar",
      data: { labels: sp.map((s) => `${s.name} (${s.up_pct}%)`), datasets: [{ data: sp.map((s) => s.chg), backgroundColor: sp.map((s) => s.chg >= 0 ? "#3ee0a1" : "#ff7b8a"), borderRadius: 4 }] },
      options: { indexAxis: "y", maintainAspectRatio: false, plugins: { legend: { display: false }, tooltip: { callbacks: { label: (c) => ` ${sgn(c.raw, 2, "%")}` } } },
        scales: { x: { ticks: { color: "#98acd0", callback: (v) => v + "%" }, grid: { color: "#3a5890" } }, y: { ticks: { color: "#f5f8ff", font: { size: 13 } }, grid: { display: false } } } } });
    $("#view").querySelectorAll("[data-go]").forEach((x) => x.onclick = (e) => { e.stopPropagation(); S.tab = x.dataset.go; render(); });
    bindInfo();
  }

  // ---------------------------------------------------------------- 트랜드캐치·유동성 공통
  function rawFmt(kind, m, i) {
    const p = kind === "tc" ? "tc_" : "lq_";
    const v = at(p + m.key, i);
    if (v == null) return "—";
    if (kind === "lq" && m.key === "y10") { const c = at("lq_y10_chg", i); return `${n2(v, 2)}% <small class="sub">(13주 ${sgn(c, 0, "bp")})</small>`; }
    return (SIGNED.has(m.key) ? sgn(v, m.dec) : n2(v, m.dec)) + m.unit;
  }
  const MANUAL = new Set(["fg", "pc", "aaii", "margin"]);
  function obsFor(kind, key, i) {
    if (MANUAL.has(key)) return at("obs_" + key, i);
    if (i !== D().length - 1 || !S.latest.asof) return null;
    const k2 = kind === "lq" && key === "hy" ? "lq_hy" : key === "y10" ? "us10y" : key;
    return S.latest.asof[k2] || null;
  }
  function tiles(kind, list, i) {
    const p = kind === "tc" ? "s_tc_" : "s_lq_", L = kind === "tc" ? M.TC_LABELS : M.LQ_LABELS, col = kind === "tc" ? (s) => TCC[s - 1] : (s) => LQC[s - 1];
    const j = i - 5;
    return list.map((m) => {
      const s = at(p + m.key, i), s0 = at(p + m.key, j);
      const arrow = s == null || s0 == null ? "" : s > s0 ? `<span class="up">▲${s - s0}</span>` : s < s0 ? `<span class="down">▼${s0 - s}</span>` : `<span class="flat">-</span>`;
      const ob = obsFor(kind, m.key, i), obTxt = ob && ob !== D()[i] ? `<span class="ob">${short(ob)} 기준</span>` : "";
      return `<div class="tile ${s == null ? "stale" : ""}" data-info="${kind}:${m.key}"><div class="n">${m.name}</div><div class="v num">${rawFmt(kind, m, i)}${obTxt}</div>
        <div class="f">${s ? `<span class="pill" style="background:${col(s)}">${s} ${L[s]}</span>` : pill(null)}<span>${m.w ? `<span class="w">${m.w}% · </span>` : ""}1주 전 ${arrow || "—"}</span></div></div>`;
    }).join("");
  }
  function compositeCard(kind, i) {
    const v = at(kind, i), lab = kind === "tc" ? labelTC(v) : labelLQ(v), col = kind === "tc" ? colTC(lab) : colLQ(lab);
    const j = i - 5, v0 = at(kind, j), Z = kind === "tc" ? TC_Z : LQ_Z, CC = kind === "tc" ? TCC : LQC;
    const act = kind === "tc" ? M.TC_ACTION[lab] : M.LQ_STANCE[lab];
    const pos = v == null ? null : Math.max(0, Math.min(100, (v - 1) / 4 * 100));
    const cov = kind === "tc" ? `9개 중 ${at("tc_n", i) ?? 0}개 지표로 계산` : `가중치 ${n2(at("lq_w", i), 1)}% 반영`;
    return `<div class="card click" data-info="${kind}:_comp"><h3 class="${kind}h">${kind === "tc" ? "트랜드캐치" : "유동성"} 종합 · ${short(D()[i])}</h3>
      <div style="display:flex;align-items:center;gap:12px;margin-top:8px"><span class="big num" style="color:${col}">${v ?? "—"}</span>
        <div>${pill(lab, col)}<div style="margin-top:4px;font-size:14px">${act ? (kind === "tc" ? "매매 판단: " : "유동성 환경: ") + act : ""}</div></div></div>
      <div class="scale">${CC.map((c) => `<div style="background:${c}"></div>`).join("")}</div>
      <div class="marker">${pos == null ? "" : `<i style="left:${pos}%"></i>`}</div>
      <div class="scalelb">${Z.map((z) => `<span>${z}</span>`).join("")}</div>
      <div class="note">${v0 != null && v != null ? `1주 전 ${v0} → ${v > v0 ? "+" : ""}${(v - v0).toFixed(1)}` : ""} · ${cov}</div>
      <div class="cap" style="margin:14px 0 4px">최근 3개월 추이</div><div class="chartbox" style="height:150px"><canvas id="cmini"></canvas></div></div>`;
  }
  function quadrant(i, cm) {
    const W = 320, H = 210, x0 = 40, y0 = 10, w = 266, h = 170;
    const X = (v) => x0 + (v - 1) / 4 * w, Y = (v) => y0 + h - (v - 1) / 4 * h;
    const pts = weekEnds(i, 9).map((k) => ({ k, x: at("lq", k), y: at("tc", k) })).filter((p) => p.x != null && p.y != null);
    const poly = pts.map((p) => `${X(p.x)},${Y(p.y)}`).join(" ");
    const cur = pts[pts.length - 1];
    const auto = cur ? `심리 ${cur.y}(${labelTC(cur.y)}) · 유동성 ${cur.x}(${labelLQ(cur.x)}) — ${cur.x >= 3 ? (cur.y >= 3 ? "돈도 넉넉하고 심리도 달아오른 구간" : "돈은 넉넉한데 심리는 식은 구간") : (cur.y >= 3 ? "돈은 줄어드는데 심리는 뜨거운 구간" : "돈도 줄고 심리도 식은 구간")}` : "";
    return `<div class="card"><h3>심리 × 유동성 사분면</h3><div class="cap">최근 9주 궤적 · 가로 = 유동성, 세로 = 트랜드캐치</div>
      <svg viewBox="0 0 ${W} ${H + 18}" width="100%" style="max-width:440px;display:block;margin:0 auto" role="img" aria-label="사분면">
        <rect x="${x0}" y="${y0}" width="${w / 2}" height="${h / 2}" fill="#5a2c42"/><rect x="${x0 + w / 2}" y="${y0}" width="${w / 2}" height="${h / 2}" fill="#5a4626"/>
        <rect x="${x0}" y="${y0 + h / 2}" width="${w / 2}" height="${h / 2}" fill="#2a3a5e"/><rect x="${x0 + w / 2}" y="${y0 + h / 2}" width="${w / 2}" height="${h / 2}" fill="#1d5a55"/>
        <text x="${x0 + 6}" y="${y0 + 14}" fill="#f4a3b4" font-size="11">위험: 돈↓ 심리↑</text><text x="${x0 + w - 6}" y="${y0 + 14}" fill="#f5c58a" font-size="11" text-anchor="end">과열 주의: 돈↑ 심리↑</text>
        <text x="${x0 + 6}" y="${y0 + h - 6}" fill="#c6d4ee" font-size="11">바닥 탐색: 돈↓ 심리↓</text><text x="${x0 + w - 6}" y="${y0 + h - 6}" fill="#7fe0c9" font-size="11" text-anchor="end">기회: 돈↑ 심리↓</text>
        ${[1, 2, 3, 4, 5].map((v) => `<text x="${X(v)}" y="${y0 + h + 14}" fill="#98acd0" font-size="10" text-anchor="middle">${v}</text><text x="${x0 - 8}" y="${Y(v) + 3}" fill="#98acd0" font-size="10" text-anchor="end">${v}</text>`).join("")}
        <polyline points="${poly}" fill="none" stroke="#a5b4fc" stroke-width="1.5" stroke-dasharray="3 2"/>
        ${pts.slice(0, -1).map((p, n) => `<circle cx="${X(p.x)}" cy="${Y(p.y)}" r="${2 + n * 0.25}" fill="#a5b4fc" opacity="${0.35 + n * 0.07}"><title>${D()[p.k]}: 심리 ${p.y} / 유동성 ${p.x}</title></circle>`).join("")}
        ${cur ? `<circle cx="${X(cur.x)}" cy="${Y(cur.y)}" r="6" fill="#e9c46a" stroke="#16264a" stroke-width="2"/><text x="${X(cur.x) + 9}" y="${Y(cur.y) - 7}" fill="#e9c46a" font-size="11">${short(D()[cur.k])}</text>` : ""}
      </svg>
      <div class="qc"><b>종합</b>${esc(cm?.quad || auto)}</div></div>`;
  }
  function heatmap(kind, list, i) {
    const cols = weekEnds(i, 12), p = kind === "tc" ? "s_tc_" : "s_lq_", CC = kind === "tc" ? TCC : LQC;
    const head = `<div></div>` + cols.map((k) => `<div class="hd">${short(D()[k])}</div>`).join("");
    const row = (nm, key, comp) => `<div class="rl">${nm}</div>` + cols.map((k) => {
      const v = comp ? at(kind, k) : at(p + key, k);
      if (v == null) return `<div class="cl na ${k === i ? "sel" : ""}" data-d="${D()[k]}">·</div>`;
      const s = comp ? Math.min(5, Math.max(1, Math.round(v))) : v;
      return `<div class="cl ${k === i ? "sel" : ""}" data-d="${D()[k]}" style="background:${CC[s - 1]}" title="${nm} ${D()[k]}: ${v}">${comp ? v : v}</div>`;
    }).join("");
    return `<div class="card"><h3 class="${kind}h">지표별 점수 히트맵</h3><div class="cap">주 마지막 거래일 기준 최근 12주 · 칸을 누르면 그 날짜로 이동 · ${kind === "tc" ? "파랑 = 공포, 빨강 = 광기" : "갈색 = 경색, 청록 = 풍부"}</div>
      <div class="hmwrap"><div class="hm" style="grid-template-columns:96px repeat(${cols.length},minmax(30px,1fr))">${head}${list.map((m) => row(m.short || m.name, m.key)).join("")}${row("종합", null, true)}</div></div></div>`;
  }
  function corrBlock(kind) {
    const Z = kind === "tc" ? TC_Z : LQ_Z;
    return `<div class="card sec"><h3 class="${kind}h">지수와의 상관</h3>
      <div class="cap">주간 기준. 막대 = 점수 구간별 이후 평균 수익률, 선 = 점수와 지수 흐름, 아래 = 26주 이동 상관 (점수 vs 이후 4주 수익률)</div>
      <div class="ctl"><div class="seg" id="segIdx">${Object.entries(IDX_NAME).map(([k, v]) => `<button data-v="${k}" class="${S.idx === k ? "on" : ""}">${v}</button>`).join("")}</div>
        <div class="seg" id="segH">${["1", "4", "12"].map((h) => `<button data-v="${h}" class="${S.h === h ? "on" : ""}">이후 ${h}주</button>`).join("")}</div>
        <div class="seg" id="segR">${[["1y", "1년"], ["3y", "3년"]].map(([k, v]) => `<button data-v="${k}" class="${S.range === k ? "on" : ""}">${v}</button>`).join("")}</div></div>
      <div class="grid g2"><div><div class="chartbox"><canvas id="cbar"></canvas></div><div class="note" id="cnote"></div></div>
        <div><div class="chartbox"><canvas id="cline"></canvas></div><div class="chartbox sm" style="margin-top:8px"><canvas id="croll"></canvas></div></div></div>
      <div class="note">${kind === "tc" ? "트랜드캐치 과거값은 웹에서 확인하는 4개 지표(F&G·AAII·풋콜·신용융자)의 과거 기록이 부족해 대부분 5~6개 지표로 계산됐습니다. 매일 쌓이면서 정확해집니다." : "유동성은 신용융자 과거 기록이 2026년 5월부터라 그 전은 나머지 지표 가중치로 다시 나눠 계산했습니다."} 코스피는 미국 t일 다음 한국 거래일 종가로 맞췄습니다. 과거 관계가 앞으로도 같다는 보장은 없습니다.</div></div>`;
  }
  function bandPlugin(CC) {
    return { id: "bands", beforeDraw(ch) { const { ctx, chartArea: a, scales: { y } } = ch; if (!a) return;
      const cuts = [1, 1.5, 2.5, 3.5, 4.5, 5]; ctx.save();
      for (let z = 0; z < 5; z++) { const t = y.getPixelForValue(cuts[z + 1]), b = y.getPixelForValue(cuts[z]); ctx.fillStyle = CC[z] + "22"; ctx.fillRect(a.left, t, a.right - a.left, b - t); }
      ctx.restore(); } };
  }
  function drawMini(kind, i) {
    killChart("cmini"); const el = $("#cmini"); if (!el) return;
    const CC = kind === "tc" ? TCC : LQC, s = Math.max(0, i - 62), ds = D().slice(s, i + 1);
    charts.cmini = new Chart(el, { type: "line", plugins: [bandPlugin(CC)],
      data: { labels: ds, datasets: [{ data: ds.map((_, n) => at(kind, s + n)), borderColor: kind === "tc" ? "#f59e6b" : "#0fb9a5", borderWidth: 2, pointRadius: 0, stepped: true, spanGaps: true }] },
      options: { maintainAspectRatio: false, plugins: { legend: { display: false }, tooltip: { callbacks: { label: (c) => ` ${c.raw} ${kind === "tc" ? labelTC(c.raw) : labelLQ(c.raw)}` } } },
        scales: { x: { ticks: { color: "#98acd0", maxTicksLimit: 4, callback: function (v) { return short(this.getLabelForValue(v)); } }, grid: { display: false } },
          y: { min: 1, max: 5, ticks: { color: "#98acd0", stepSize: 1 }, grid: { color: "#3a5890" } } } } });
  }
  function drawCorr(kind, i) {
    const Z = kind === "tc" ? TC_Z : LQ_Z, CC = kind === "tc" ? TCC : LQC;
    const cr = S.corr && S.corr[kind] && S.corr[kind][S.idx];
    killChart("cbar"); killChart("cline"); killChart("croll");
    if (!cr) return;
    const bk = cr.buckets[S.h] || {};
    charts.cbar = new Chart($("#cbar"), { type: "bar",
      data: { labels: Z, datasets: [{ data: Z.map((z) => bk[z]?.mean ?? null), backgroundColor: CC, borderRadius: 4 }] },
      options: { maintainAspectRatio: false, plugins: { legend: { display: false }, title: { display: true, text: `${IDX_NAME[S.idx]} 이후 ${S.h}주 평균 수익률 (%)`, color: "#c6d4ee", font: { size: 12 } },
        tooltip: { callbacks: { label: (c) => { const b = bk[Z[c.dataIndex]]; return b ? ` 평균 ${b.mean}% · 상승 확률 ${b.win}% · ${b.n}주` : " 표본 없음"; } } } },
        scales: { x: { ticks: { color: "#c6d4ee" }, grid: { display: false } }, y: { ticks: { color: "#98acd0", callback: (v) => v + "%" }, grid: { color: "#3a5890" } } } } });
    const ic = cr.ic[S.h];
    $("#cnote").innerHTML = `순위상관 ${ic == null ? "—" : ic}. ${ic == null ? "" : ic < -0.1 ? "점수가 높을수록 이후 수익률이 낮았습니다 (역발상이 통함)." : ic > 0.1 ? "점수가 높을수록 이후 수익률도 높았습니다 (순방향)." : "뚜렷한 관계가 없었습니다."} 막대에 마우스를 올리면 상승 확률과 표본 수가 보입니다.`;
    // 선 차트: 주간 샘플
    const ds = D(), we = weekEnds(i, S.range === "1y" ? 53 : 160);
    const pxKey = S.idx === "kospi" ? "kospi" : S.idx;
    const bands = bandPlugin(CC);
    charts.cline = new Chart($("#cline"), { type: "line", plugins: [bands],
      data: { labels: we.map((k) => ds[k]), datasets: [
        { label: kind === "tc" ? "트랜드캐치" : "유동성", data: we.map((k) => at(kind, k)), borderColor: kind === "tc" ? "#f59e6b" : "#0fb9a5", borderWidth: 2, pointRadius: 0, stepped: true, yAxisID: "y", spanGaps: true },
        { label: IDX_NAME[S.idx], data: we.map((k) => at(pxKey, k)), borderColor: "#e8eef8", borderWidth: 1.4, pointRadius: 0, yAxisID: "y2", spanGaps: true }] },
      options: { maintainAspectRatio: false, interaction: { mode: "index", intersect: false },
        plugins: { legend: { labels: { color: "#c6d4ee", boxWidth: 12 } } },
        scales: { x: { ticks: { color: "#98acd0", maxTicksLimit: 6, callback: function (v) { return this.getLabelForValue(v).slice(2, 7); } }, grid: { display: false } },
          y: { min: 1, max: 5, ticks: { color: "#98acd0", stepSize: 1 }, grid: { color: "#3a5890" }, title: { display: true, text: "점수", color: "#98acd0" } },
          y2: { position: "right", ticks: { color: "#98acd0" }, grid: { display: false } } } } });
    const rl = cr.rolling, cut = S.range === "1y" ? 53 : 160;
    const rd = rl.dates.slice(-cut), rv = rl.v.slice(-cut);
    charts.croll = new Chart($("#croll"), { type: "line",
      data: { labels: rd, datasets: [{ label: "26주 이동 상관", data: rv, borderColor: "#e9c46a", borderWidth: 1.6, pointRadius: 0, fill: { target: { value: 0 }, above: "#34d39933", below: "#ff6b7a33" }, spanGaps: true }] },
      options: { maintainAspectRatio: false, plugins: { legend: { labels: { color: "#c6d4ee", boxWidth: 12 } } },
        scales: { x: { ticks: { color: "#98acd0", maxTicksLimit: 6, callback: function (v) { return this.getLabelForValue(v).slice(2, 7); } }, grid: { display: false } },
          y: { min: -1, max: 1, ticks: { color: "#98acd0", stepSize: 0.5 }, grid: { color: "#3a5890" } } } } });
  }
  function bindCorr(kind, i) {
    [["#segIdx", "idx"], ["#segH", "h"], ["#segR", "range"]].forEach(([sel, key]) => {
      $(sel).querySelectorAll("button").forEach((b) => b.onclick = () => { S[key] = b.dataset.v; $(sel).querySelectorAll("button").forEach((x) => x.classList.toggle("on", x === b)); drawCorr(kind, i); });
    });
    drawCorr(kind, i);
  }

  async function viewTC() {
    const i = idxOf(S.date), cm = (await comments(D()[i])) || {};
    $("#view").innerHTML = `<div class="grid g2">${compositeCard("tc", i)}${quadrant(i, cm)}</div>
      ${cm.tc ? `<div class="oneliner"><span class="lb">트랜드캐치 코멘트</span><span class="tx">${esc(cm.tc)}</span></div>` : ""}
      <div class="card sec"><h3 class="tch">9개 지표</h3><div class="cap">타일을 누르면 계산 방법과 의미가 나옵니다 · 점수 5 = 광기, 1 = 공포</div>
        <div class="grid tg" style="margin-top:8px">${tiles("tc", M.tc, i)}</div></div>
      <div class="sec">${heatmap("tc", M.tc, i)}</div>${corrBlock("tc")}${analysisBlock("tc")}`;
    bindInfo(); bindHeat(); bindCorr("tc", i); drawMini("tc", i); bindAnalysis("tc");
  }
  async function viewLQ() {
    const i = idxOf(S.date), cm = (await comments(D()[i])) || {};
    const byCat = ["A", "B", "C", "D"].map((c) => `<div class="catlb">${c}. ${M.LQ_CATS[c]}</div><div class="grid tg">${tiles("lq", M.lq.filter((m) => m.cat === c), i)}</div>`).join("");
    // 카테고리 기여도
    const contrib = ["A", "B", "C", "D"].map((c) => {
      const ms = M.lq.filter((m) => m.cat === c); let ws = 0, sc = 0;
      ms.forEach((m) => { const s = at("s_lq_" + m.key, i); if (s != null) { ws += m.w; sc += s * m.w; } });
      return { c, avg: ws ? sc / ws : null, w: ms.reduce((a, m) => a + m.w, 0) };
    });
    const bar = contrib.map((x) => `<div style="flex:${x.w};background:${x.avg ? LQC[Math.round(x.avg) - 1] : "#334155"}" title="${M.LQ_CATS[x.c]} 평균 ${x.avg ? x.avg.toFixed(1) : "—"}">${x.c} ${x.avg ? x.avg.toFixed(1) : "—"}</div>`).join("");
    $("#view").innerHTML = `<div class="grid g2">${compositeCard("lq", i)}${quadrant(i, cm)}</div>
      ${cm.lq ? `<div class="oneliner" style="border-color:#0fb9a5"><span class="lb" style="color:#5fd3b0">유동성 코멘트</span><span class="tx">${esc(cm.lq)}</span></div>` : ""}
      <div class="card sec"><h3 class="lqh">카테고리별 점수</h3><div class="cap">막대 폭 = 가중치, 색 = 카테고리 평균 판단</div><div class="contrib">${bar}</div></div>
      <div class="card sec"><h3 class="lqh">11개 지표</h3><div class="cap">타일을 누르면 계산 방법과 의미가 나옵니다 · 점수 5 = 풍부, 1 = 경색 · 타일의 % = 가중치</div>${byCat}</div>
      <div class="sec">${heatmap("lq", M.lq, i)}</div>${corrBlock("lq")}${analysisBlock("lq")}`;
    bindInfo(); bindHeat(); bindCorr("lq", i); drawMini("lq", i); bindAnalysis("lq");
  }
  function bindHeat() { $("#view").querySelectorAll(".hm .cl[data-d]").forEach((c) => c.onclick = () => setDate(c.dataset.d)); }

  // ---------------------------------------------------------------- 예측력 분석
  const PK = ["−26주", "−13주", "−8주", "−4주", "직전 4주", "+4주", "+8주", "+13주", "+26주"];
  function aCell(v, sig) {
    if (v == null) return `<td class="c muted">—</td>`;
    const a = Math.min(1, Math.abs(v) * 2.2), bg = v >= 0 ? `rgba(62,224,161,${a * 0.55})` : `rgba(255,123,138,${a * 0.55})`;
    return `<td class="c" style="background:${bg}">${v > 0 ? "+" : ""}${v.toFixed(2)}${sig ? "★" : ""}</td>`;
  }
  function analysisBlock(kind) {
    if (!S.analysis) return "";
    return `<div class="card sec"><h3 class="${kind}h">지표별 예측력 · 선행 / 후행 분석</h3>
      <div class="cap">${S.analysis.start.slice(0, 4)}년 이후 주간 자료 · 숫자는 순위상관(−1~+1) · <b>+</b> 점수가 높을수록 이후 수익률이 높았음 · <b>−</b> 점수가 높을수록 이후 수익률이 낮았음(역발상) · ★ 겹치는 기간을 감안해도 통계적으로 의미 있음 · 행을 누르면 시차별 그래프</div>
      <div class="ctl"><div class="seg" id="segA">${[["spx", "S&P500"], ["ndx", "나스닥100"]].map(([k, v]) => `<button data-v="${k}" class="${S.aidx === k ? "on" : ""}">${v}</button>`).join("")}</div></div>
      <div style="overflow-x:auto"><table class="st at" id="atable"></table></div>
      <div class="note" id="asum"></div>
      <div class="note">읽는 법: '이후 4주·13주'가 크면 앞으로를 설명하는 <b>선행</b> 지표, '지난 13주 반영'이 크면 이미 지나간 흐름을 비추는 <b>후행</b> 지표입니다. 분석 기간 ${S.analysis.start} ~ ${S.analysis.end}, 공개 지연을 반영해 그 시점에 알 수 있던 값만 썼습니다. 과거 관계가 앞으로도 같다는 보장은 없습니다.</div></div>`;
  }
  function drawAnalysis(kind) {
    const el = $("#atable"); if (!el || !S.analysis) return;
    const list = (kind === "tc" ? M.tc : M.lq).map((m) => ({ key: `${kind}_${m.key}`, name: m.name, mkey: m.key })).concat([{ key: kind, name: (kind === "tc" ? "트랜드캐치" : "유동성") + " 종합", mkey: "_comp" }]);
    const rows = list.map((x) => {
      const it = S.analysis.items[x.key], r = it && it[S.aidx];
      if (!r) return `<tr><td>${x.name}</td><td colspan="7" class="muted">${esc(S.analysis.na[x.mkey] || "자료 없음")}</td></tr>`;
      return `<tr class="click" data-ak="${x.key}" data-an="${esc(x.name)}"><td>${x.name}</td><td class="muted">${r.start.slice(0, 7)}</td>${["1", "4", "13", "26"].map((h) => aCell(r.ic[h], r.sig[h])).join("")}${aCell(r.past13, false)}<td>${esc(r.role)}<div class="muted" style="font-size:12px">${esc(r.direction)}${r.stable ? "" : " · 전·후반 부호 다름"}</div></td></tr>`;
    }).join("");
    el.innerHTML = `<tr><th>지표</th><th>자료 시작</th><th class="r">이후 1주</th><th class="r">이후 4주</th><th class="r">이후 13주</th><th class="r">이후 26주</th><th class="r">지난 13주 반영</th><th>판정</th></tr>${rows}`;
    el.querySelectorAll("[data-ak]").forEach((tr) => tr.onclick = () => openAnalysis(tr.dataset.ak, tr.dataset.an));
    const ok = list.map((x) => ({ n: x.name, r: S.analysis.items[x.key]?.[S.aidx] })).filter((x) => x.r && x.r.weeks >= 300);
    const hv = (r) => r.sig["13"] ? ["13", r.ic["13"]] : ["4", r.ic["4"]];
    const lead = ok.filter((x) => x.r.sig["13"] || x.r.sig["4"]).sort((a, b) => Math.abs(hv(b.r)[1]) - Math.abs(hv(a.r)[1]));
    const lag = ok.filter((x) => Math.abs(x.r.past13 || 0) >= 0.3).map((x) => x.n);
    $("#asum").innerHTML = `요약 (${S.aidx === "spx" ? "S&P500" : "나스닥100"}, 6년 이상 자료만): 통계적으로 의미 있는 선행 지표는 ${lead.length ? lead.map((x) => { const [h, v] = hv(x.r); return `${x.n}(이후 ${h}주 ${v > 0 ? "+" : ""}${v})`; }).join(", ") : "없음"}입니다. 지난 흐름을 크게 반영하는 후행 성격은 ${lag.length ? lag.join(", ") : "없음"}입니다.`;
  }
  function bindAnalysis(kind) {
    if (!$("#segA")) return;
    $("#segA").querySelectorAll("button").forEach((b) => b.onclick = () => { S.aidx = b.dataset.v; $("#segA").querySelectorAll("button").forEach((x) => x.classList.toggle("on", x === b)); drawAnalysis(kind); });
    drawAnalysis(kind);
  }
  function analysisText(r) {
    const f = (v) => v == null ? "—" : (v > 0 ? "+" : "") + v.toFixed(2);
    return `이후 4주 ${f(r.ic["4"])}${r.sig["4"] ? "★" : ""} · 이후 13주 ${f(r.ic["13"])}${r.sig["13"] ? "★" : ""} · 지난 13주 반영 ${f(r.past13)} → <b>${esc(r.role)}</b>${r.direction ? ", " + esc(r.direction) : ""}${r.half ? ` (전반 ${f(r.half[0])} / 후반 ${f(r.half[1])})` : ""}`;
  }
  function openAnalysis(key, name) {
    const it = S.analysis.items[key];
    $("#mbox").innerHTML = `<button class="x" aria-label="닫기">×</button><h2>${esc(name)} · 시차별 관계</h2>
      <div class="ctl" style="margin-top:8px"><div class="seg" id="segA2">${[["spx", "S&P500"], ["ndx", "나스닥100"]].map(([k, v]) => `<button data-v="${k}" class="${S.aidx === k ? "on" : ""}">${v}</button>`).join("")}</div></div>
      <div class="chartbox" style="height:230px"><canvas id="aprof"></canvas></div>
      <p id="atext" style="margin-top:8px"></p>
      <h4>그래프 읽는 법</h4><p>막대 하나는 '이 지표 값'과 '어느 시점에 끝나는 4주 수익률'의 순위상관입니다. 왼쪽(−)은 지표보다 먼저 일어난 수익률, 오른쪽(+)은 지표 이후의 수익률입니다. 왼쪽이 길면 지난 흐름을 따라가는 후행 지표, 오른쪽이 길면 앞으로를 설명하는 선행 지표입니다. 부호는 점수 방향 기준입니다(+ = 점수가 높을 때 수익률도 높음).</p>`;
    $("#modal").classList.add("on"); $("#mbox .x").onclick = closeInfo;
    const draw = () => {
      const r = it[S.aidx]; killChart("aprof");
      charts.aprof = new Chart($("#aprof"), { type: "bar", data: { labels: PK, datasets: [{ data: r.profile, backgroundColor: r.profile.map((v, n) => n < 5 ? "#98acd0" : (v >= 0 ? "#3ee0a1" : "#ff7b8a")), borderRadius: 3 }] },
        options: { maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { y: { min: -0.8, max: 0.8, ticks: { color: "#98acd0" }, grid: { color: "#3a5890" } }, x: { ticks: { color: "#c6d4ee" }, grid: { display: false } } } } });
      $("#atext").innerHTML = `${S.aidx === "spx" ? "S&P500" : "나스닥100"} · 자료 ${r.start} 이후 ${r.weeks}주: ` + analysisText(r);
    };
    $("#segA2").querySelectorAll("button").forEach((b) => b.onclick = () => { S.aidx = b.dataset.v; $("#segA2").querySelectorAll("button").forEach((x) => x.classList.toggle("on", x === b)); draw(); });
    draw();
  }

  // ---------------------------------------------------------------- 휴대폰 알림 (OneSignal 웹 푸시)
  function initPush() {
    const btn = $("#pushbtn"); if (!btn) return;
    const ios = /iPhone|iPad|iPod/.test(navigator.userAgent), standalone = window.navigator.standalone === true || matchMedia("(display-mode: standalone)").matches;
    const setLabel = (OS) => { const on = OS && OS.User && OS.User.PushSubscription && OS.User.PushSubscription.optedIn; btn.textContent = on ? "알림 켜짐" : "알림 받기"; btn.classList.toggle("on", !!on); };
    const ready = () => { btn.hidden = false; setLabel(window.__seoksPush); };
    if (window.__seoksPush) ready(); else document.addEventListener("seoks-push-ready", ready);
    if (ios && !standalone) { btn.hidden = false; btn.textContent = "알림 받기"; }
    btn.onclick = async () => {
      if (ios && !standalone) {
        $("#mbox").innerHTML = `<button class="x" aria-label="닫기">×</button><h2>아이폰에서 알림 받기</h2><p>아이폰은 홈 화면에 추가한 Seoks에서만 알림을 받을 수 있습니다 (iOS 16.4 이상).</p><h4>방법</h4><p>1. Safari 아래쪽 공유 버튼을 누릅니다.<br>2. '홈 화면에 추가'를 누릅니다.<br>3. 홈 화면의 Seoks 아이콘으로 열고, 오른쪽 위 '알림 받기'를 누릅니다.</p>`;
        $("#modal").classList.add("on"); $("#mbox .x").onclick = closeInfo; return;
      }
      const OS = window.__seoksPush; if (!OS) return;
      try { await OS.Notifications.requestPermission(); if (!OS.User.PushSubscription.optedIn) await OS.User.PushSubscription.optIn(); } catch (e) { console.warn(e); }
      setLabel(OS);
    };
  }

  // ---------------------------------------------------------------- 새 소식
  const LS = { get: (k) => { try { return localStorage.getItem(k); } catch (e) { return null; } }, set: (k, v) => { try { localStorage.setItem(k, v); } catch (e) {} } };
  function initBell() {
    const boards = S.latest.boards || [], last = boards[boards.length - 1];
    let seen = LS.get("seoks_seen");
    if (!seen && last) { LS.set("seoks_seen", last); seen = last; }
    const unread = boards.filter((d) => seen && d > seen).length;
    const cnt = $("#bellcnt"); if (unread) { cnt.textContent = unread; cnt.hidden = false; } else cnt.hidden = true;
    $("#bell").onclick = async (e) => {
      e.stopPropagation();
      const box = $("#newsp"); if (!box.hidden) { box.hidden = true; return; }
      const recent = boards.slice(-7).reverse();
      box.innerHTML = `<h4>새 소식</h4><div class="muted" style="font-size:12px">불러오는 중…</div>`; box.hidden = false;
      const items = await Promise.all(recent.map(async (d) => ({ d, c: await comments(d) })));
      box.innerHTML = `<h4>새 소식</h4>` + (items.length ? items.map(({ d, c }) => `<div class="it ${seen && d > seen ? "new" : ""}" data-d="${d}"><div class="d">${d} (${dow(d)}) 미국 마감</div>${esc((c && ((c.market && c.market.headline) || c.oneliner)) || "현황판 업데이트")}</div>`).join("") : `<div class="muted">아직 소식이 없습니다.</div>`)
        + `<div class="muted" style="font-size:11.5px;margin-top:8px">매일 아침(한국 시간 6시대) 업데이트됩니다. 휴대폰에서는 '홈 화면에 추가'하면 앱처럼 열 수 있습니다.</div>`;
      box.querySelectorAll("[data-d]").forEach((x) => x.onclick = () => { box.hidden = true; S.tab = "board"; setDate(x.dataset.d); });
      if (last) { LS.set("seoks_seen", last); seen = last; } cnt.hidden = true;
    };
    document.addEventListener("click", (e) => { const box = $("#newsp"); if (box && !box.hidden && !e.target.closest("#newsp")) box.hidden = true; });
  }

  // ---------------------------------------------------------------- 설명 모달
  function bindInfo() { $("#view").querySelectorAll("[data-info]").forEach((el) => el.onclick = () => openInfo(el.dataset.info)); }
  function openInfo(spec) {
    const [kind, key] = spec.split(":"), i = idxOf(S.date), d = D()[i], isLast = i === D().length - 1;
    let h = "";
    if (kind === "tc" || kind === "lq") {
      if (key === "_comp") h = compInfo(kind, i);
      else {
        const m = (kind === "tc" ? M.tc : M.lq).find((x) => x.key === key);
        const s = at((kind === "tc" ? "s_tc_" : "s_lq_") + key, i), L = kind === "tc" ? M.TC_LABELS : M.LQ_LABELS, col = kind === "tc" ? TCC : LQC;
        const obs = obsFor(kind, key, i);
        h = `<h2>${m.name}</h2><div class="sub">${kind === "tc" ? "트랜드캐치" : "유동성 · " + M.LQ_CATS[m.cat] + " · 가중치 " + m.w + "%"}</div>
          <div class="cur"><span class="v num">${rawFmt(kind, m, i)}</span>${s ? `<span class="pill" style="background:${col[s - 1]}">${s}점 · ${L[s]}</span>` : pill(null)}<span class="muted">${short(d)} 기준${obs ? ` · 관측일 ${obs}` : ""}</span></div>
          <h4>무엇인가요</h4><p>${m.desc}</p><h4>계산 방법</h4><p>${m.formula}</p>
          <h4>점수 구간</h4><table>${m.bins.map(([r, sc]) => `<tr class="${sc === s ? "hit" : ""}"><td>${r}</td><td style="text-align:right">${sc == null ? "" : sc + "점 · " + L[sc]}</td></tr>`).join("")}</table>
          ${m.evidence ? `<div class="ev">${m.evidence}</div>` : ""}
          <h4>오르면 / 내리면</h4><p>${m.up}<br>${m.down}</p>
          ${(() => { const it = S.analysis && S.analysis.items[`${kind}_${key}`]; if (!it) return S.analysis && S.analysis.na[key] ? `<h4>예측력</h4><p class="sub">${esc(S.analysis.na[key])}</p>` : "";
            return `<h4>예측력 (${S.analysis.start.slice(0, 4)}년~)</h4><p>S&P500: ${analysisText(it.spx)}</p><p style="margin-top:4px">나스닥100: ${analysisText(it.ndx)}</p>`; })()}
          <div class="src">출처: <a href="${m.src.url}" target="_blank" rel="noopener">${m.src.name}</a> · 갱신 ${m.freq}${s == null ? "<br>이 날짜에는 값이 없거나 너무 오래된 값이라 점수에서 뺐습니다." : ""}</div>`;
      }
    } else {
      const m = M.board[key] || M.board.index;
      const b = S.boards[d], val = b && b.breadth && b.breadth[key] != null ? b.breadth[key] : null;
      h = `<h2>${m.name}</h2>${val != null ? `<div class="cur"><span class="v num">${typeof val === "number" && !Number.isInteger(val) ? n2(val, 1) + "%" : Number(val).toLocaleString()}</span><span class="muted">${short(d)} 기준</span></div>` : ""}
        <h4>무엇인가요</h4><p>${m.desc}</p><h4>계산 방법</h4><p>${m.formula}</p>`;
    }
    $("#mbox").innerHTML = `<button class="x" aria-label="닫기">×</button>${h}`;
    $("#modal").classList.add("on");
    $("#mbox .x").onclick = closeInfo;
  }
  function compInfo(kind, i) {
    const v = at(kind, i);
    if (kind === "tc") {
      const rows = M.tc.map((m) => { const s = at("s_tc_" + m.key, i); return `<tr><td>${m.name}</td><td style="text-align:right">${s ?? "—"}</td></tr>`; }).join("");
      return `<h2>트랜드캐치 종합</h2><div class="cur"><span class="v num">${v ?? "—"}</span>${pill(labelTC(v), colTC(labelTC(v)))}<span class="muted">${short(D()[i])} 기준</span></div>
        <h4>계산 방법</h4><p>9개 지표 점수(1~5)의 단순평균, 소수 첫째 자리 반올림. 값이 있는 지표가 5개 이상일 때만 계산합니다.</p>
        <table>${rows}</table><h4>판단 구간</h4><table>${[["4.5 ~ 5.0", "광기"], ["3.5 ~ 4.5", "과열"], ["2.5 ~ 3.5", "중립"], ["1.5 ~ 2.5", "불안"], ["1.0 ~ 1.5", "공포"]].map(([r, l]) => `<tr class="${l === labelTC(v) ? "hit" : ""}"><td>${r}</td><td>${l}</td><td style="text-align:right">${M.TC_ACTION[l]}</td></tr>`).join("")}</table>`;
    }
    const rows = M.lq.map((m) => { const s = at("s_lq_" + m.key, i); return `<tr><td>${m.cat}. ${m.name}</td><td style="text-align:right">${m.w}%</td><td style="text-align:right">${s ?? "—"}</td></tr>`; }).join("");
    return `<h2>유동성 종합</h2><div class="cur"><span class="v num">${v ?? "—"}</span>${pill(labelLQ(v), colLQ(labelLQ(v)))}<span class="muted">${short(D()[i])} 기준</span></div>
      <h4>계산 방법</h4><p>11개 지표 점수의 가중평균 (A 양 35% · B 가격 25% · C 활용 20% · D 결과 20%). 값이 없는 지표는 빼고 나머지 가중치로 다시 나눕니다 (전체 가중치의 70% 이상 있을 때만 계산).</p>
      <p class="sub" style="margin-top:6px">원본 시트 대비 변경: VIX 제외(그 몫은 D 안에서 비례 배분), 10년물을 5점 척도로 바꿔 D에 편입, DXY·10년물·EFFR 기준 재설정.</p>
      <table><tr><td class="muted">지표</td><td class="muted" style="text-align:right">가중치</td><td class="muted" style="text-align:right">점수</td></tr>${rows}</table>
      <h4>판단 구간</h4><table>${[["4.5 ~ 5.0", "풍부"], ["3.5 ~ 4.5", "우호"], ["2.5 ~ 3.5", "중립"], ["1.5 ~ 2.5", "긴축"], ["1.0 ~ 1.5", "경색"]].map(([r, l]) => `<tr class="${l === labelLQ(v) ? "hit" : ""}"><td>${r}</td><td>${l}</td><td style="text-align:right">${M.LQ_STANCE[l]}</td></tr>`).join("")}</table>`;
  }
  function closeInfo() { $("#modal").classList.remove("on"); }
  $("#modal").onclick = (e) => { if (e.target.id === "modal") closeInfo(); };
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") { closeInfo(); if (S.calOpen) { S.calOpen = false; renderDatebar(); } }
    if ($("#modal").classList.contains("on")) return;
    if (e.key === "ArrowLeft") step(-1); if (e.key === "ArrowRight") step(1);
  });

  // ---------------------------------------------------------------- 렌더
  async function render() {
    if (idxOf(S.date) < 0) S.date = D()[D().length - 1];
    S.date = D()[idxOf(S.date)];
    document.querySelectorAll(".tab").forEach((t) => t.classList.toggle("on", t.dataset.t === S.tab));
    const nm = { board: "미국 증시 현황", tc: "트랜드캐치", lq: "유동성" }[S.tab];
    $("#title").textContent = `${nm} | ${fmtDateKo(S.date)} 마감`;
    const isLast = S.date === S.latest.date;
    $("#stamp").textContent = isLast ? `${S.latest.generated} 업데이트` : `${S.date}(${dow(S.date)}) 기록 보기`;
    writeURL(); renderDatebar();
    Object.keys(charts).forEach(killChart);
    if (S.tab === "board") await viewBoard(); else if (S.tab === "tc") await viewTC(); else await viewLQ();
  }
  document.querySelectorAll(".tab").forEach((t) => t.onclick = () => { S.tab = t.dataset.t; render(); });
  document.addEventListener("click", (e) => { if (S.calOpen && !e.target.closest(".cal") && e.target.id !== "calbtn") { S.calOpen = false; renderDatebar(); } });

  async function init() {
    try {
      S.latest = await (await fetch("data/latest.json?t=" + Date.now())).json();
      [S.series, S.corr, S.analysis, S.notes] = await Promise.all([getJSON("data/series.json"), getJSON("data/corr.json").catch(() => null), getJSON("data/analysis.json").catch(() => null), getJSON("data/notes/companies.json").catch(() => ({}))]);
    } catch (e) {
      $("#view").innerHTML = `<div class="empty">데이터를 불러오지 못했습니다. 잠시 후 새로고침해 주세요.</div>`; return;
    }
    readURL();
    if (!S.date) S.date = S.latest.date;
    if (Chart && Chart.defaults) { Chart.defaults.font.family = getComputedStyle(document.body).fontFamily; Chart.defaults.color = "#c6d4ee"; }
    initBell(); initPush();
    render();
  }
  init();
})();
