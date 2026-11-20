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
  const GOOD = "#3ee0a1", BAD = "#ff7b8a", MID = "#a9b6cf";
  const TABS = ["wind", "board", "tc", "lq"];
  const TAB_NM = { wind: "증시 풍향계", board: "미국 증시 현황", tc: "트렌드캐치", lq: "유동성" };

  const S = { tab: "wind", date: null, idx: "ndx", h: "4", range: "3y", calOpen: false, calMonth: null, aidx: "spx", analysis: null, notes: {},
    series: null, corr: null, latest: null, wind: null, windIdx: null, boards: {}, comments: {}, hist: null,
    t40: { k: "mcap", dir: -1 }, wrange: "1y", brange: "1y" };
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
  const fmtDateKo = (d) => { const [, m, dd] = d.split("-").map(Number); return `${m}월 ${dd}일`; };
  const dow = (d) => "일월화수목금토"[new Date(d + "T00:00:00").getDay()];
  const short = (d) => { const [, m, dd] = d.split("-"); return `${+m}/${+dd}`; };
  const indKo = (x) => (x && M.IND_KO[x]) || x || "";

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
    while (k >= 0 && out.length < count) { if (wk(ds[k]) !== cur) { out.push(k); cur = wk(ds[k]); } k--; }
    return out.reverse();
  }
  function lastN(k, i, n) { const a = C(k), out = []; for (let j = i; j >= 0 && out.length < n; j--) if (a[j] != null) out.unshift({ d: D()[j], v: a[j] }); return out; }
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
  const axisX = (n = 6) => ({ ticks: { color: "#98acd0", maxTicksLimit: n, maxRotation: 0, callback: function (v) { const l = this.getLabelForValue(v); return l.slice(2, 7).replace("-", "."); } }, grid: { display: false } });

  // ---------------------------------------------------------------- 풍향계 값
  const windAt = (i) => { if (!S.wind || i < 0) return null; const k = S.windIdx.get(D()[i]); return k == null ? null : S.wind.w[k]; };
  const windPart = (key, i) => { if (!S.wind || i < 0) return null; const k = S.windIdx.get(D()[i]); return k == null ? null : S.wind[key][k]; };
  function zoneOf(v) {
    if (v == null || !S.wind) return { name: "자료 없음", act: "—", color: "#475569" };
    let z = S.wind.zones[0]; S.wind.zones.forEach((x) => { if (v >= x.from) z = x; }); return z;
  }

  // ---------------------------------------------------------------- 상태·URL
  function readURL() {
    const p = new URLSearchParams(location.search);
    if (TABS.includes(p.get("tab"))) S.tab = p.get("tab");
    if (p.get("date")) S.date = p.get("date");
  }
  function writeURL() {
    const p = new URLSearchParams(); p.set("tab", S.tab); if (S.date !== S.latest.date) p.set("date", S.date);
    history.replaceState(null, "", "?" + p.toString());
  }
  function setDate(d) { S.date = d; S.calOpen = false; render(); }
  function step(n) { const i = idxOf(S.date) + n; if (i >= 0 && i < D().length) setDate(D()[i]); }
  function goTab(t) { S.tab = t; render(); window.scrollTo({ top: 0, behavior: "smooth" }); }

  // ---------------------------------------------------------------- 날짜 바·달력
  function dotColor(i) {
    if (S.tab === "lq") { const l = labelLQ(at("lq", i)); return l ? colLQ(l) : "#334155"; }
    if (S.tab === "tc") { const l = labelTC(at("tc", i)); return l ? colTC(l) : "#334155"; }
    const v = windAt(i); return v == null ? "#334155" : zoneOf(v).color;
  }
  const dotName = () => S.tab === "lq" ? "유동성" : S.tab === "tc" ? "트렌드캐치" : "풍향계";
  function renderDatebar() {
    const ds = D(), i = idxOf(S.date), last = ds.length - 1;
    const e = last - i <= 4 ? last : i, s = Math.max(0, e - 4);
    const chips = [];
    for (let k = s; k <= e; k++) {
      const d = ds[k], bd = S.latest.boards.includes(d);
      chips.push(`<button class="chip ${k === i ? "on" : ""}" data-d="${d}" title="${d}${bd ? " · 현황판 있음" : ""}"><span class="dot" style="background:${dotColor(k)}"></span>${short(d)} ${dow(d)}</button>`);
    }
    $("#datebar").innerHTML =
      `<button class="chip nav" id="prev" ${i <= 0 ? "disabled" : ""} aria-label="이전 거래일">‹</button>${chips.join("")}
       <button class="chip nav" id="next" ${i >= last ? "disabled" : ""} aria-label="다음 거래일">›</button>
       ${i !== last ? `<button class="chip" id="today">최신으로</button>` : ""}
       <span class="sp"></span><span class="muted dlg">점 색 = 그날 ${dotName()}</span>`;
    $("#datebar").querySelectorAll("[data-d]").forEach((b) => b.onclick = () => setDate(b.dataset.d));
    $("#prev").onclick = () => step(-1); $("#next").onclick = () => step(1);
    if ($("#today")) $("#today").onclick = () => setDate(ds[last]);
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
    return `<div class="cal"><div class="ch"><button id="cprev" ${S.calMonth <= minM ? "disabled" : ""} aria-label="이전 달">‹</button><span>${y}년 ${m}월</span><button id="cnext" ${S.calMonth >= maxM ? "disabled" : ""} aria-label="다음 달">›</button></div>
      <div class="grid">${cells}</div><div class="lg">날짜를 누르면 그날 기록으로 바뀝니다 · 점 = 그날 ${dotName()} 색 · 금색 테두리 = 현황판 기록이 있는 날</div></div>`;
  }
  function renderCalPop() {
    const box = $("#calpop"); if (!box) return;
    box.innerHTML = S.calOpen ? renderCal() : "";
    $("#calbtn").classList.toggle("on", S.calOpen);
    if (!S.calOpen) return;
    $("#cprev").onclick = (e) => { e.stopPropagation(); S.calMonth = addMonth(S.calMonth, -1); renderCalPop(); };
    $("#cnext").onclick = (e) => { e.stopPropagation(); S.calMonth = addMonth(S.calMonth, 1); renderCalPop(); };
    box.querySelectorAll(".d.has").forEach((b) => b.onclick = () => setDate(b.dataset.d));
  }

  // ---------------------------------------------------------------- 공통 위젯
  function spark(arr, col) {
    const v = (arr || []).filter((x) => x != null); if (v.length < 2) return "";
    const mn = Math.min(...v), mx = Math.max(...v), w = 100, h = 30;
    const pts = v.map((x, k) => `${(k / (v.length - 1)) * w},${h - 3 - ((x - mn) / (mx - mn || 1)) * (h - 6)}`).join(" ");
    return `<svg class="spark" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none"><polyline points="${pts}" fill="none" stroke="${col}" stroke-width="1.6" vector-effect="non-scaling-stroke"/></svg>`;
  }
  // 최근 6거래일 종가 차트: 점선 = 전일 종가(값 표시), 초록 = 주식에 좋은 방향
  function idxChart(p, goodUp, fmt) {
    if (!p || p.length < 2) return "";
    const v = p.map((x) => x.v), base = v[v.length - 2], last = v[v.length - 1];
    const mn = Math.min(...v), mx = Math.max(...v), w = 100, h = 46, pad = 6;
    const Y = (y) => pad + (h - 2 * pad) * (1 - (y - mn) / (mx - mn || 1));
    const X = (k) => (k / (v.length - 1)) * w;
    const good = goodUp ? last >= base : last <= base, col = last === base ? MID : good ? GOOD : BAD;
    const pts = v.map((y, k) => `${X(k)},${Y(y)}`).join(" ");
    const area = `0,${h} ${pts} ${w},${h}`;
    const by = (Y(base) / h) * 100;
    return `<div class="ich"><svg viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" aria-hidden="true">
        <polygon points="${area}" fill="${col}" opacity=".10"/>
        <line x1="0" x2="${w}" y1="${Y(base)}" y2="${Y(base)}" stroke="#b9c7e4" stroke-width="1" stroke-dasharray="3 3" vector-effect="non-scaling-stroke"/>
        <polyline points="${pts}" fill="none" stroke="${col}" stroke-width="2" vector-effect="non-scaling-stroke" stroke-linejoin="round"/></svg>
        <i class="ich-dot" style="top:${(Y(last) / h) * 100}%;background:${col}"></i>
        <span class="ich-bl ${by < 30 ? "below" : ""}" style="top:${by}%">전일 ${fmt(base)}</span></div>
      <div class="ich-x"><span>${short(p[0].d)}</span><span>최근 6거래일</span><span>${short(p[p.length - 1].d)}</span></div>`;
  }
  const TONE_NM = { up: "좋음", down: "나쁨", flat: "중립" };
  const toneTag = (t) => TONE_NM[t] ? `<em class="tn t-${t}">${TONE_NM[t]}</em>` : "";
  function pointsBlock(title, pts, kind) {
    if (!pts || !pts.length) return "";
    return `<div class="card sec pts ${kind || ""}"><h3>${title}</h3><ol>${pts.map((p, n) => `<li class="${TONE_NM[p.tone] ? "t-" + p.tone : ""}"><span class="no">${n + 1}</span><div>${p.h ? `<b>${toneTag(p.tone)}${esc(p.h)}</b>` : ""}<p>${esc(p.t)}</p></div></li>`).join("")}</ol>
      <div class="note">숫자에 근거한 판단 보조입니다. 투자 권유가 아니며, 결정은 각자 하셔야 합니다.</div></div>`;
  }
  function scenarioBlock(sc, title = "앞으로 이렇게 되면") {
    if (!sc || !sc.length) return "";
    return `<div class="card sec scen"><h3>${title}</h3><div class="cap">어떤 숫자가 어떻게 바뀌면 판단이 달라지는지 미리 정해 둔 기준입니다 · 초록 = 좋아지는 경우, 빨강 = 나빠지는 경우</div>
      <div class="scl">${sc.map((s) => `<div class="sc t-${TONE_NM[s.tone] ? s.tone : "flat"}"><div class="if"><span>만약</span>${esc(s.if)}</div><div class="then"><span>그러면</span>${esc(s.then)}</div></div>`).join("")}</div></div>`;
  }
  const icWords = (ic) => { if (ic == null) return "자료 없음"; const a = Math.abs(ic); return (M.EXPLAIN.ic_words.find(([lim]) => a < lim) || [0, ""])[1]; };
  function rankCorr(a, b) {
    const pr = []; a.forEach((x, k) => { if (x != null && b[k] != null) pr.push([x, b[k]]); });
    if (pr.length < 30) return null;
    const rk = (v) => { const o = v.map((x, k) => [x, k]).sort((p, q) => p[0] - q[0]), r = new Array(v.length); let s = 0;
      while (s < o.length) { let e = s; while (e + 1 < o.length && o[e + 1][0] === o[s][0]) e++; for (let m = s; m <= e; m++) r[o[m][1]] = (s + e) / 2; s = e + 1; } return r; };
    const x = rk(pr.map((p) => p[0])), y = rk(pr.map((p) => p[1])), n = x.length, mx = x.reduce((s, v) => s + v, 0) / n, my = y.reduce((s, v) => s + v, 0) / n;
    let sxy = 0, sxx = 0, syy = 0; for (let k = 0; k < n; k++) { sxy += (x[k] - mx) * (y[k] - my); sxx += (x[k] - mx) ** 2; syy += (y[k] - my) ** 2; }
    return sxx && syy ? sxy / Math.sqrt(sxx * syy) : null;
  }
  const asPoints = (arr, fallback) => (arr && arr.length) ? arr.map((x) => typeof x === "string" ? { h: "", t: x } : x) : (fallback ? [{ h: "", t: fallback }] : []);
  function bandPlugin(CC) {
    return { id: "bands", beforeDraw(ch) { const { ctx, chartArea: a, scales: { y } } = ch; if (!a) return;
      const cuts = [1, 1.5, 2.5, 3.5, 4.5, 5]; ctx.save();
      for (let z = 0; z < 5; z++) { const t = y.getPixelForValue(cuts[z + 1]), b = y.getPixelForValue(cuts[z]); ctx.fillStyle = CC[z] + "22"; ctx.fillRect(a.left, t, a.right - a.left, b - t); }
      ctx.restore(); } };
  }
  function hlinePlugin(lines, axis = "y") {
    return { id: "hlines", beforeDatasetsDraw(ch) { const { ctx, chartArea: a } = ch, sc = ch.scales[axis]; if (!a || !sc) return; ctx.save();
      lines.forEach(([v, lab, col]) => { const y = sc.getPixelForValue(v); if (y < a.top || y > a.bottom) return;
        ctx.strokeStyle = col || "#6f86b5"; ctx.setLineDash([4, 4]); ctx.lineWidth = 1; ctx.beginPath(); ctx.moveTo(a.left, y); ctx.lineTo(a.right, y); ctx.stroke();
        if (lab) { ctx.setLineDash([]); ctx.fillStyle = col || "#98acd0"; ctx.font = "11px sans-serif"; ctx.fillText(lab, a.left + 4, y - 4); } });
      ctx.restore(); } };
  }

  // ---------------------------------------------------------------- 사분면 (트렌드캐치·풍향계 탭)
  const QZ = { "기회": "분할 매수 검토", "과열 주의": "추격 매수 자제", "위험": "비중 점검·현금 여유", "바닥 탐색": "돈 풀림 신호 기다리기" };
  const quadName = (p) => p.x >= 3 ? (p.y >= 3 ? "과열 주의" : "기회") : (p.y >= 3 ? "위험" : "바닥 탐색");
  function quadAdvice(pts) {
    const cur = pts[pts.length - 1]; if (!cur) return "";
    const old = pts[Math.max(0, pts.length - 5)], dx = cur.x - old.x, dy = cur.y - old.y, nm = quadName(cur);
    const base = {
      "기회": "돈은 넉넉한데 심리는 식어 있는 자리입니다. 겁이 많을 때가 오히려 분할 매수에 유리했던 구간입니다.",
      "과열 주의": "돈도 넉넉하고 심리도 달아오른 자리입니다. 보유는 유지하되 추격 매수는 줄이고, 심리가 4(과열)를 넘으면 이익 일부 확정을 검토할 때입니다.",
      "위험": "돈은 줄어드는데 심리는 뜨거운 자리입니다. 가장 조심할 구간이라 비중을 점검하고 현금 여유를 두는 쪽이 낫습니다.",
      "바닥 탐색": "돈도 줄고 심리도 식은 자리입니다. 급하게 팔기보다 유동성이 3 위로 돌아서는 신호를 기다리며 분할 매수를 준비할 때입니다.",
    }[nm];
    let mv = "";
    if (Math.abs(dx) >= 0.2 || Math.abs(dy) >= 0.2) {
      if (dx < 0 && dy > 0) mv = " 최근 4주는 '위험' 쪽(돈↓ 심리↑)으로 움직이고 있어 조심할 신호입니다.";
      else if (dx > 0 && dy < 0) mv = " 최근 4주는 '기회' 쪽(돈↑ 심리↓)으로 움직이고 있습니다.";
      else if (dy > 0) mv = " 최근 4주 심리가 달아오르는 중입니다.";
      else if (dy < 0) mv = " 최근 4주 심리가 식는 중입니다.";
    }
    return base + mv;
  }
  function mix(a, b, t) {
    const p = (h) => [1, 3, 5].map((k) => parseInt(h.slice(k, k + 2), 16));
    const A = p(a), B = p(b); return "#" + A.map((x, k) => Math.round(x + (B[k] - x) * t).toString(16).padStart(2, "0")).join("");
  }
  function quadrant(i, cm) {
    const sm = window.innerWidth < 600, zoom = S.qzoom !== false;
    const W = sm ? 360 : 500, H = sm ? 350 : 372, x0 = sm ? 50 : 62, y0 = 12, w = W - x0 - 14, h = sm ? 260 : 290;
    const F = sm ? { z: 15, zh: 12, t: 13, ax: 13, cur: 14 } : { z: 14, zh: 12, t: 12, ax: 13, cur: 13 };
    const pts = weekEnds(i, 9).map((k) => ({ k, x: at("lq", k), y: at("tc", k) })).filter((p) => p.x != null && p.y != null);
    const fit = (arr) => { let lo = Math.min(...arr) - 0.22, hi = Math.max(...arr) + 0.22; if (hi - lo < 1.0) { const m = (lo + hi) / 2; lo = m - 0.5; hi = m + 0.5; }
      return [Math.max(1, Math.floor(lo * 4) / 4), Math.min(5, Math.ceil(hi * 4) / 4)]; };
    const [xa, xb] = zoom && pts.length ? fit(pts.map((p) => p.x).concat([2.7, 3.3])) : [1, 5];
    const [ya, yb] = zoom && pts.length ? fit(pts.map((p) => p.y).concat([2.7, 3.3])) : [1, 5];
    const X = (v) => x0 + (v - xa) / (xb - xa) * w, Y = (v) => y0 + h - (v - ya) / (yb - ya) * h;
    const n = pts.length, cur = pts[n - 1];
    const tcol = (m) => mix("#6f7fa6", "#f5cf6a", n > 1 ? m / (n - 1) : 1);
    let segs = "";
    for (let m = 1; m < n; m++) {
      const a = pts[m - 1], b = pts[m]; let ax = X(a.x), ay = Y(a.y), bx = X(b.x), by = Y(b.y);
      const L = Math.hypot(bx - ax, by - ay); if (L < 14) continue;
      const ux = (bx - ax) / L, uy = (by - ay) / L, rEnd = m === n - 1 ? 12 : 8;
      ax += ux * 6; ay += uy * 6; bx -= ux * rEnd; by -= uy * rEnd;
      segs += `<line x1="${ax}" y1="${ay}" x2="${bx}" y2="${by}" stroke="${tcol(m)}" stroke-width="${1.8 + m * 0.25}" marker-end="url(#qa${m === n - 1 ? "2" : ""})" opacity="${0.55 + 0.45 * (m / (n - 1 || 1))}"/>`;
    }
    const dots = pts.map((p, m) => m === n - 1 ? "" : `<circle cx="${X(p.x)}" cy="${Y(p.y)}" r="${3.5 + m * 0.45}" fill="${tcol(m)}" stroke="#16264a" stroke-width="1"><title>${D()[p.k]}: 트렌드캐치 ${p.y} / 유동성 ${p.x}</title></circle>`).join("");
    const zl = (x, y, anc, nm, col) => `<text x="${x}" y="${y}" fill="${col}" font-size="${F.z}" font-weight="700" text-anchor="${anc}">${nm}</text><text x="${x}" y="${y + F.zh + 5}" fill="${col}" font-size="${F.zh}" opacity=".85" text-anchor="${anc}">${QZ[nm]}</text>`;
    const tk = (a, b) => { const st = (b - a) <= 2.5 ? 0.5 : 1, o = []; for (let v = Math.ceil(a / st) * st; v <= b + 1e-9; v += st) o.push(+v.toFixed(1)); return o; };
    const first = pts[0], mx = X(3), my = Y(3);
    const curRight = cur && X(cur.x) > x0 + w * 0.7;
    return `<div class="card quad"><div class="mh"><h3>심리 × 유동성 사분면</h3><button class="lnk" id="qzoom">${zoom ? "전체(1~5) 보기" : "확대해서 보기"}</button></div>
      <div class="cap">점 하나 = 한 주(주 마지막 거래일) · 최근 ${n}주 궤적${zoom ? ` · 점이 모인 범위를 확대함 (유동성 ${xa}~${xb}, 심리 ${ya}~${yb})` : ""}</div>
      <svg viewBox="0 0 ${W} ${H}" width="100%" style="display:block" role="img" aria-label="심리와 유동성 사분면">
        <defs><marker id="qa" viewBox="0 0 10 10" refX="8" refY="5" markerUnits="userSpaceOnUse" markerWidth="9" markerHeight="9" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="#c8b37a"/></marker>
          <marker id="qa2" viewBox="0 0 10 10" refX="8" refY="5" markerUnits="userSpaceOnUse" markerWidth="11" markerHeight="11" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="#f5cf6a"/></marker></defs>
        <rect x="${x0}" y="${y0}" width="${mx - x0}" height="${my - y0}" fill="#5a2c42"/><rect x="${mx}" y="${y0}" width="${x0 + w - mx}" height="${my - y0}" fill="#5a4626"/>
        <rect x="${x0}" y="${my}" width="${mx - x0}" height="${y0 + h - my}" fill="#2a3a5e"/><rect x="${mx}" y="${my}" width="${x0 + w - mx}" height="${y0 + h - my}" fill="#1d5a55"/>
        <line x1="${mx}" x2="${mx}" y1="${y0}" y2="${y0 + h}" stroke="#a9b8d8" stroke-dasharray="4 4" opacity=".7"/><line x1="${x0}" x2="${x0 + w}" y1="${my}" y2="${my}" stroke="#a9b8d8" stroke-dasharray="4 4" opacity=".7"/>
        ${zl(x0 + 8, y0 + F.z + 6, "start", "위험", "#ffb3c1")}${zl(x0 + w - 8, y0 + F.z + 6, "end", "과열 주의", "#ffd28f")}
        ${zl(x0 + 8, y0 + h - F.zh - 14, "start", "바닥 탐색", "#cdd9f2")}${zl(x0 + w - 8, y0 + h - F.zh - 14, "end", "기회", "#86ecd3")}
        ${tk(xa, xb).map((v) => `<text x="${X(v)}" y="${y0 + h + F.t + 4}" fill="${v === 3 ? "#ffe08a" : "#c6d4ee"}" font-size="${F.t}" text-anchor="middle">${v}</text>`).join("")}
        ${tk(ya, yb).map((v) => `<text x="${x0 - 7}" y="${Y(v) + 4}" fill="${v === 3 ? "#ffe08a" : "#c6d4ee"}" font-size="${F.t}" text-anchor="end">${v}</text>`).join("")}
        <text x="${x0 + w / 2}" y="${H - 6}" fill="#e6edfb" font-size="${F.ax}" text-anchor="middle">유동성 점수 →  (낮음 경색 · 3 중립 · 높음 풍부)</text>
        <text x="14" y="${y0 + h / 2}" fill="#e6edfb" font-size="${F.ax}" text-anchor="middle" transform="rotate(-90 14 ${y0 + h / 2})">트렌드캐치 점수 →  (낮음 공포 · 높음 광기)</text>
        ${segs}${dots}
        ${first && n > 1 ? `<text x="${X(first.x)}" y="${Y(first.y) + (Y(first.y) > y0 + h - 20 ? -12 : 20)}" fill="#c3cfe8" font-size="${F.t - 1}" text-anchor="middle">${n - 1}주 전</text>` : ""}
        ${cur ? `<circle cx="${X(cur.x)}" cy="${Y(cur.y)}" r="9.5" fill="#f5cf6a" stroke="#16264a" stroke-width="2.5"><title>${D()[cur.k]}: 트렌드캐치 ${cur.y} / 유동성 ${cur.x}</title></circle>
          <text x="${X(cur.x) + (curRight ? -14 : 14)}" y="${Y(cur.y) + (Y(cur.y) < y0 + 30 ? 22 : -12)}" fill="#ffe08a" font-size="${F.cur}" font-weight="800" text-anchor="${curRight ? "end" : "start"}" paint-order="stroke" stroke="#16264a" stroke-width="3">${short(D()[cur.k])} (심리 ${cur.y}, 유동성 ${cur.x})</text>` : ""}
      </svg>
      <div class="qlg"><span><i style="background:#6f7fa6"></i>${n - 1}주 전</span><span class="arr">→</span><span><i style="background:#f5cf6a"></i>이번 주</span><span class="muted">· 점이 진해질수록 최근 · 화살표 = 움직인 방향 · 점선 = 중립선 3</span></div>
      <div class="qc"><b>판단 보조</b>${esc((cm && cm.quad) || quadAdvice(pts))}</div></div>`;
  }
  function bindQuad(i, cm) {
    const b = $("#qzoom"); if (!b) return;
    b.onclick = (e) => { e.stopPropagation(); S.qzoom = S.qzoom === false; const card = $(".quad"); card.outerHTML = quadrant(i, cm); bindQuad(i, cm); };
  }

  // ---------------------------------------------------------------- 증시 풍향계 탭
  function gauge(v) {
    const cx = 170, cy = 158, r = 124, sw = 28;
    const ang = (x) => Math.PI * (1 - x / 100);
    const pt = (x, rr) => [cx + rr * Math.cos(ang(x)), cy - rr * Math.sin(ang(x))];
    const zs = S.wind.zones, bounds = zs.map((z) => z.from).concat([100]);
    const arcs = zs.map((z, k) => { const [x1, y1] = pt(bounds[k] + 0.4, r), [x2, y2] = pt(bounds[k + 1] - 0.4, r);
      return `<path d="M${x1},${y1} A${r},${r} 0 0 1 ${x2},${y2}" stroke="${z.color}" stroke-width="${sw}" fill="none" opacity="${v != null && v >= bounds[k] && v < bounds[k + 1] + (k === zs.length - 1 ? 1 : 0) ? 1 : 0.38}"/>`; }).join("");
    const labs = zs.map((z, k) => { const m = (bounds[k] + bounds[k + 1]) / 2, [x, y] = pt(m, r + sw / 2 + 12);
      return `<text x="${x}" y="${y + 4}" fill="#dfe7f7" font-size="12" text-anchor="middle">${z.name}</text>`; }).join("");
    const nd = v == null ? "" : (() => { const [x, y] = pt(v, r - sw / 2 - 8); return `<line x1="${cx}" y1="${cy}" x2="${x}" y2="${y}" stroke="#f5f8ff" stroke-width="5" stroke-linecap="round"/><circle cx="${cx}" cy="${cy}" r="10" fill="#f5f8ff"/>`; })();
    return `<svg viewBox="0 0 340 178" width="100%" class="gauge" role="img" aria-label="풍향계 ${v ?? ""}점">${arcs}${labs}
      <text x="${pt(0, r)[0]}" y="${cy + 18}" fill="#98acd0" font-size="11" text-anchor="middle">0</text><text x="${pt(100, r)[0]}" y="${cy + 18}" fill="#98acd0" font-size="11" text-anchor="middle">100</text>${nd}</svg>`;
  }
  function autoWindHead(v, v0, i) {
    if (v == null) return "풍향계를 계산할 자료가 부족합니다.";
    const z = zoneOf(v), t = at("tc", i), l = at("lq", i);
    const mv = v0 == null ? "" : v > v0 + 1 ? " 1주 전보다 순풍 쪽으로 움직였습니다." : v < v0 - 1 ? " 1주 전보다 역풍 쪽으로 움직였습니다." : " 1주 전과 큰 차이가 없습니다.";
    return `심리 ${t}(${labelTC(t)}) · 유동성 ${l}(${labelLQ(l)}) → 풍향계 ${v}점 '${z.name}'.${mv}`;
  }
  function windCards(b, i) {
    const tcv = at("tc", i), lqv = at("lq", i);
    const ix = (k) => { const p = lastN(k, i, 2); return p.length < 2 ? null : (p[1].v / p[0].v - 1) * 100; };
    const spx = ix("spx"), ndx = ix("ndx"), kospi = ix("kospi");
    const tone = (g) => g == null ? "flat" : g > 0 ? "up" : g < 0 ? "down" : "flat";
    const cards = [];
    cards.push({ go: "board", tone: tone(spx == null ? null : Math.abs(spx) < 0.25 ? 0 : spx), tag: "오늘 시장", title: `S&P500 ${sgn(spx, 2, "%")}`, sub: `나스닥100 ${sgn(ndx, 2, "%")} · 코스피 ${sgn(kospi, 2, "%")}` });
    const tl = labelTC(tcv);
    cards.push({ go: "tc", tone: tcv == null ? "flat" : tcv <= 2.5 ? "up" : tcv >= 3.5 ? "down" : "flat", tag: "심리 (트렌드캐치)", title: `${tcv ?? "—"} ${tl || ""}`,
      sub: tcv == null ? "" : tcv <= 2.5 ? "겁이 많은 때 → 역발상 매수 기회 쪽" : tcv >= 3.5 ? "달아오른 때 → 추격 매수 조심" : "과열도 공포도 아닌 보통 상태" });
    const ll = labelLQ(lqv);
    cards.push({ go: "lq", tone: lqv == null ? "flat" : lqv >= 3.5 ? "up" : lqv <= 2.5 ? "down" : "flat", tag: "유동성 (돈의 흐름)", title: `${lqv ?? "—"} ${ll || ""}`,
      sub: lqv == null ? "" : `주식에 ${M.LQ_STANCE[ll]}` });
    if (b) {
      const br = b.breadth, ratio = br.nh ? br.nl / br.nh : null;
      const t = br.nh >= br.nl * 1.5 ? "up" : br.nl >= br.nh * 1.5 ? "down" : "flat";
      cards.push({ go: "board", tone: t, tag: "시장 체력", title: `신고가 ${br.nh} · 신저가 ${br.nl}`,
        sub: `${ratio && ratio >= 1.5 ? `신저가가 신고가의 ${n2(ratio, 1)}배` : ratio && ratio <= 0.67 ? "신고가가 더 많음" : "신고가·신저가 비슷"} · S&P500 200일선 위 ${n2(br.sp500_above200, 0)}%` });
    }
    const TN = { up: "좋음", down: "나쁨", flat: "보통" };
    return `<div class="wk">${cards.map((c) => `<button class="wkc t-${c.tone}" data-go="${c.go}"><span class="tg">${c.tag}<em>${TN[c.tone]}</em></span><b>${esc(c.title)}</b><span class="sb">${esc(c.sub)}</span><span class="more">자세히 →</span></button>`).join("")}</div>`;
  }
  function zoneBounds() { const zs = S.wind.zones; return zs.map((z, k) => [z.from, k + 1 < zs.length ? zs[k + 1].from : 100]); }
  function verdictBlock(z, wc) {
    const E = (M.EXPLAIN.zones || {})[z.name] || {}, g = wc.guide || {};
    const verdict = wc.verdict || (E.mean ? `지금은 '${z.name}' — ${E.mean}입니다. ${E.buy}.` : "");
    const rows = [["새로 사기", g.buy || E.buy], ["갖고 있는 주식", g.hold || E.hold], ["조심할 것", g.watch]].filter((r) => r[1]);
    if (!verdict && !rows.length) return "";
    return `<div class="verdict" style="border-color:${z.color}"><div class="vh" style="color:${z.color}">총평</div><div class="vt">${esc(verdict)}</div>
      ${rows.length ? `<div class="vg">${rows.map(([k, v]) => `<div class="vr"><span>${k}</span><b>${esc(v)}</b></div>`).join("")}</div>` : ""}
      <div class="vn">지표에 근거한 판단 보조이며 투자 권유가 아닙니다.</div></div>`;
  }
  function windMeaning(cur) {
    const E = M.EXPLAIN, st = S.wind.stats.spx["60"] || {}, nd = (S.wind.stats.ndx || {})["60"] || {};
    const bd = zoneBounds(), rows = S.wind.zones.map((z, k) => ({ z, lo: bd[k][0], hi: bd[k][1] })).reverse();
    const past = (r, nm) => r ? `<b class="num ${cls(r.mean)}">${sgn(r.mean, 1, "%")}</b><span>오른 경우 ${n2(r.win, 0)}% · ${r.n}일</span>` : `<b class="muted">사례 없음</b><span>아직 이 구간에 온 적이 없음</span>`;
    return `<div class="card sec wmean"><h3>역풍·순풍이 뭔가요?</h3><p class="wi">${esc(E.wind_intro)}</p>
      <div class="zl"><div class="zr zh"><span>구간 (점수)</span><span>뜻</span><span>새로 사기 · 갖고 있는 주식</span><span>과거 3개월 뒤 S&P500</span></div>
      ${rows.map(({ z, lo, hi }) => { const Z = E.zones[z.name] || {};
        return `<div class="zr ${z.name === cur ? "cur" : ""}" style="--zc:${z.color}"><span class="zn"><i style="background:${z.color}"></i><b>${z.name}</b><em class="num">${lo}~${hi}</em>${z.name === cur ? `<u>지금</u>` : ""}</span>
          <span class="zm">${esc(Z.mean || "")}</span><span class="za"><b>${esc(Z.buy || "")}</b>${esc(Z.hold || "")}</span><span class="zp">${past(st[z.name])}${nd[z.name] ? `<span>나스닥100 ${sgn(nd[z.name].mean, 1, "%")}</span>` : ""}</span></div>`; }).join("")}</div>
      <div class="note">${esc(E.zone_note)} 전체 평균: S&P500 ${st["전체"] ? sgn(st["전체"].mean, 1, "%") : "—"}.</div></div>`;
  }
  // ---------------------------------------------------------------- 가중치 (data/weights.json · 매주 토요일 점검: 주간·월간·분기)
  const LVL = { weekly: "주간", monthly: "월간", quarterly: "분기", biweekly: "첫" };
  const TCK = ["fg", "aaii", "vix", "hy", "pc", "margin", "a200", "rsi", "dev"], LQK = ["fed", "nl", "m2", "effr", "hy", "dxy", "margin", "bank", "vol", "nfci", "y10"];
  // 버전에 들어 있는 지표 키(원래 지표 순서 + 새 팩터)
  function keysOf(v, kind) { const base = kind === "tc" ? TCK : LQK, o = (v && v[kind]) || {}; return base.filter((k) => k in o).concat(Object.keys(o).filter((k) => !base.includes(k))); }
  const lqCats = () => ["A", "B", "C", "D", "E"].filter((c) => M.lq.some((m) => m.cat === c));
  // 새 팩터(data/factors.json, 위원회 합의로 넣은 것)를 지표 목록에 더한다
  function addFactors(F) {
    if (!F || !F.factors) return;
    Object.entries(F.factors).forEach(([k, f]) => {
      if (f.status !== "active" || (f.group === "tc" ? M.tc : M.lq).some((m) => m.key === k)) return;
      const src = f.source || {}, up = f.direction === 1;
      const tr = { level: "값 그대로", chg: `${f.chg_days}일 전과의 차이`, pct: `${f.chg_days}일 전 대비 변화율(%)` }[f.transform || "level"];
      const L = f.group === "tc" ? M.TC_LABELS : M.LQ_LABELS;
      const m = { key: k, name: f.name, short: f.short || f.name, unit: f.unit || "", dec: f.dec ?? 2, cat: f.cat || "E", isNew: true,
        desc: f.desc || f.why, freq: f.freq || "",
        formula: `${tr}을 씁니다. 그날까지 공개된 최근 3년 값 중 지금 값이 어디쯤인지를 5등분해 1~5점을 매깁니다(값이 ${up ? "높을수록" : "낮을수록"} 점수가 높습니다).`,
        bins: [["최근 3년 중 상위 20%", up ? 5 : 1], ["상위 20~40%", up ? 4 : 2], ["중간", 3], ["하위 20~40%", up ? 2 : 4], ["하위 20%", up ? 1 : 5]],
        up: `값이 ${up ? "오르면 점수가 오릅니다" : "오르면 점수가 내립니다"} (점수 5 = ${L[5]}).`, down: `값이 ${up ? "내리면 점수가 내립니다" : "내리면 점수가 오릅니다"} (점수 1 = ${L[1]}).`,
        evidence: `${f.activated || ""}부터 위원회(Fable 2 · Opus 3) 합의로 넣은 새 팩터입니다. ${f.why || ""}`,
        src: src.type === "fred" ? { name: `FRED ${src.id}`, url: `https://fred.stlouisfed.org/series/${src.id}` } :
          src.type === "fred_ratio" ? { name: `FRED ${src.num} ÷ ${src.den}`, url: `https://fred.stlouisfed.org/series/${src.num}` } : { name: "자체 계산", url: "#" } };
      (f.group === "tc" ? M.tc : M.lq).push(m);
    });
  }
  function verAt(d) { const V = S.weights && S.weights.versions; if (!V || !V.length) return null; let v = V[0]; for (const x of V) if (x.from <= d) v = x; return v; }
  function wNorm(o, keys) { const t = keys.reduce((a, k) => a + (+o[k] || 0), 0) || 1; const r = {}; keys.forEach((k) => r[k] = (+o[k] || 0) / t * 100); return r; }
  function wOf(kind, key, i) { const v = verAt(D()[i]); if (!v) { const m = (kind === "tc" ? M.tc : M.lq).find((x) => x.key === key); return kind === "tc" ? 100 / 9 : (m ? m.w : 0); } return wNorm(v[kind], keysOf(v, kind))[key] ?? 0; }
  function sentW(i) { const v = verAt(D()[i]); return v ? +v.wind.sent : 0.6; }
  const fmtW = (x) => x == null ? "—" : String(Math.round(x * 10) / 10);
  const pctW = (x) => String(Math.round(x * 1000) / 10);
  function windCoef(s) { const r = (x) => Math.round(x * 100) / 100; return [r(125 * s - 25 * (1 - s)), r(25 * s), r(25 * (1 - s))]; }
  function windFormulaText(i) {
    const s = sentW(i), [a, b, c] = windCoef(s);
    return `풍향계 = ${pctW(s)}% × 심리 바람 + ${pctW(1 - s)}% × 유동성 바람. 심리 바람 = (5 − 트렌드캐치) ÷ 4 × 100 → 공포일수록 높음(역발상). 유동성 바람 = (유동성 − 1) ÷ 4 × 100 → 돈이 넉넉할수록 높음. 정리하면 ${a} − ${b} × 트렌드캐치 + ${c} × 유동성.`;
  }
  function weightsNote(i) {
    const v = verAt(D()[i]); if (!v) return "";
    return `${short(D()[i])}에 쓰인 가중치는 버전 ${v.v}(${v.from}부터 적용, ${v.by})입니다. 가중치는 매주 토요일 풍향계가 가리킨 방향이 맞았는지 확인해 조정하며(주간·월간·분기), 바뀌면 다음 거래일부터 적용되고 이미 나온 과거 점수는 그대로 둡니다.`;
  }
  function weightsCard(i) {
    const W = S.weights; if (!W || !W.versions) return "";
    const d = D()[i], used = verAt(d), v = W.versions[W.versions.length - 1], k = W.versions.length - 1, prev = k > 0 ? W.versions[k - 1] : null;
    const pending = S.latest && v.from > S.latest.date;
    const R = W.reviews || [], last = R.length ? R[R.length - 1] : null;
    const fdef = (key) => (S.factors && S.factors.factors && S.factors.factors[key]) || null;
    const sch = W.rules && W.rules.schedule, nm = (kind, key) => ((kind === "tc" ? M.tc : M.lq).find((m) => m.key === key) || {}).short || ((kind === "tc" ? M.tc : M.lq).find((m) => m.key === key) || {}).name || (fdef(key) || {}).short || (fdef(key) || {}).name || key;
    const row = (kind) => { const keys = keysOf(v, kind), cur = wNorm(v[kind], keys), pv = prev ? wNorm(prev[kind], keysOf(prev, kind)) : null;
      return keys.map((key) => { const dlt = pv ? cur[key] - (pv[key] ?? 0) : 0, ch = Math.abs(dlt) >= 0.05;
        const isNew = pv && !(key in pv);
        return `<span class="wtag ${ch ? (dlt > 0 ? "up" : "down") : ""}" title="${esc((v.reasons || {})[kind + "." + key] || "")}">${isNew ? "<em>새</em> " : ""}${esc(nm(kind, key))} <b>${fmtW(cur[key])}%</b>${ch && !isNew ? `<em>${dlt > 0 ? "▲" : "▼"}${fmtW(Math.abs(dlt))}%p</em>` : ""}</span>`; }).join("")
        + (pv ? Object.keys(pv).filter((k) => !(k in cur)).map((k) => `<span class="wtag down">${esc(nm(kind, k))} <b>뺌</b></span>`).join("") : ""); };
    const sDl = prev ? +v.wind.sent - +prev.wind.sent : 0;
    const reasons = Object.entries(v.reasons || {}).filter(([, t]) => t);
    const hist = W.versions.slice().reverse().map((x) => `<tr class="${x === v ? "hit" : ""}"><td>v${x.v}</td><td>${x.from}부터</td><td>심리 ${pctW(+x.wind.sent)}%</td><td>${esc(x.by || "")}</td></tr>`).join("");
    const lv = (x) => LVL[x] || "";
    const revs = R.slice().reverse().slice(0, 8).map((r) => `<tr><td>${r.date}<br><span class="muted">${lv(r.level)} 점검</span></td><td>${r.decision === "변경" ? `<b>변경</b> → v${r.version}` : "유지"}</td><td>${r.direction_note ? `<b>방향:</b> ${esc(r.direction_note)}<br>` : ""}${esc(r.summary || "")}</td></tr>`).join("");
    const dec = (W.rules && W.rules.decider) || {};
    const chk = last && last.check ? Object.entries(last.check).map(([k, c]) => `<span class="wtag">${esc(k.replace(/최근(\d+)주·/, "최근 $1주 신호의 "))} 성적: 순풍 ${esc(String(c["순풍"]).replace("평균 None%", "—"))} · 역풍 ${esc(String(c["역풍"]).replace("평균 None%", "—"))} · 같은 기간 평균 ${c["같은기간_평균%"]}% · 맞힌 횟수(평균 대비) ${esc(c["방향적중_평균대비"])}</span>`).join("") : "";
    return `<div class="card sec wts"><h3>가중치 점검 <span class="muted" style="font-weight:600;font-size:13px">· 매주 토요일 (주간·월간·분기)</span></h3>
      <div class="cap">풍향계는 증시의 방향을 미리 맞히려는 지표입니다. 매주 토요일 풍향계가 가리킨 방향이 실제로 맞았는지 확인하고, 신호마다 얼마나 무게를 둘지(가중치)를 조정합니다. 주간은 조금, 매달 첫 토요일(월간)은 더, 분기 첫 달(분기)은 가장 크게 움직일 수 있습니다. 결정은 가장 최신 Claude 모델${dec.name ? `(지금 ${esc(dec.name)})` : ""}이, 적용은 Claude Opus가 합니다. 새 팩터를 넣거나 빼는 일은 Fable 2명·Opus 3명 위원회가 합의한 것만 반영합니다. 바뀌면 다음 거래일부터 적용되고, 이미 나온 과거 점수는 그대로입니다.</div>
      <div class="wvh"><span class="pill" style="background:#3b5b99">버전 ${v.v}</span><span>${v.from}부터 적용${pending ? " (다음 거래일부터)" : ""} · ${esc(v.by || "")}</span>${last ? `<span class="muted">최근 점검 ${last.date} (${lv(last.level)} · ${last.decision})</span>` : `<span class="muted">아직 점검 전</span>`}${sch && sch.next ? `<span class="muted">다음 점검 ${sch.next} (${lv(sch.next_level)})</span>` : ""}</div>
      ${last && last.direction_note ? `<div class="wsum"><b>방향 점검 (${last.date})</b> ${esc(last.direction_note)}</div>` : ""}
      ${chk ? `<div class="wtags" style="margin:4px 0 6px">${chk}</div>` : ""}
      ${v.summary ? `<div class="wsum">${esc(v.summary)}</div>` : ""}
      ${v.factors && v.factors.committee ? `<div class="wsum"><b>새 팩터 위원회(Fable 2 · Opus 3) 합의</b> ${esc(v.factors.committee)}</div>` : ""}
      ${used && used !== v ? `<div class="note" style="margin:4px 0">${short(d)} 점수는 버전 ${used.v} 가중치로 계산됐습니다(이미 나온 점수는 바꾸지 않습니다).</div>` : ""}
      ${last && last.decision === "유지" && last.version === v.v && last.summary && last.summary !== v.summary ? `<div class="wsum">${esc(last.date)} 점검: ${esc(last.summary)}</div>` : ""}
      <div class="wgrp"><div class="wgl">풍향계 = 심리 <b>${pctW(+v.wind.sent)}%</b>${Math.abs(sDl) > 1e-9 ? `<em class="${sDl > 0 ? "up" : "down"}">${sDl > 0 ? "▲" : "▼"}${pctW(Math.abs(sDl))}%p</em>` : ""} + 유동성 <b>${pctW(1 - +v.wind.sent)}%</b></div></div>
      <div class="wgrp"><div class="wgl">트렌드캐치 ${keysOf(v, "tc").length}개</div><div class="wtags">${row("tc")}</div></div>
      <div class="wgrp"><div class="wgl">유동성 ${keysOf(v, "lq").length}개</div><div class="wtags">${row("lq")}</div></div>
      ${reasons.length ? `<details class="wdet"><summary>바꾼 이유 (${reasons.length})</summary><ul>${reasons.map(([key, t]) => `<li><b>${esc(key === "wind" ? "풍향계 비중" : key.includes(".") ? (key.startsWith("tc.") ? "트렌드캐치 · " : "유동성 · ") + nm(key.slice(0, 2), key.slice(3)) : key)}</b> ${esc(t)}</li>`).join("")}</ul></details>` : ""}
      ${revs ? `<details class="wdet"><summary>점검 기록</summary><table>${revs}</table></details>` : ""}
      <details class="wdet"><summary>가중치 버전 (${W.versions.length})</summary><table>${hist}</table></details>
      <div class="note">${esc((W.rules && W.rules["안내"]) || "")} 과거 관계가 앞으로도 같다는 보장은 없습니다.</div></div>`;
  }

  async function viewWind() {
    const i = idxOf(S.date), d = D()[i], b = await board(d), cm = (await comments(d)) || {};
    const v = windAt(i), z = zoneOf(v), v0 = windAt(i - 5), wc = cm.wind || {};
    const sent = windPart("sent", i), liq = windPart("liq", i);
    const part = (nm, val, col, note) => `<div class="wp"><div class="wpn">${nm}<span class="num">${val == null ? "—" : n2(val, 0)}</span></div><div class="wpb"><i style="width:${val ?? 0}%;background:${col}"></i></div><div class="wpt">${note}</div></div>`;
    const tcv = at("tc", i), lqv = at("lq", i), E = M.EXPLAIN;
    const autoPts = [
      { h: `풍향계 ${v ?? "—"}점, '${z.name}'`, t: `${z.act} 구간입니다. 높을수록(순풍) 이후 지수가 좋았고, 낮을수록(역풍) 조심할 때였습니다.` },
      { h: `심리 ${tcv ?? "—"} ${labelTC(tcv) || ""}`, t: (cm.tc_summary || (typeof cm.tc === "string" ? cm.tc : "")) || "트렌드캐치 탭에서 지표별로 볼 수 있습니다." },
      { h: `유동성 ${lqv ?? "—"} ${labelLQ(lqv) || ""}`, t: (cm.lq_summary || (typeof cm.lq === "string" ? cm.lq : "")) || "유동성 탭에서 지표별로 볼 수 있습니다." },
    ];
    const W = S.wmode || "same";
    let html = `<div class="grid g2 wtop">
      <div class="card wcard"><h3>증시 풍향계 · ${short(d)}</h3><div class="cap">0 = 강한 역풍(매우 조심) · 100 = 강한 순풍(적극) · <button class="lnk" data-jump="wmean">역풍·순풍이 뭔가요?</button> · <button class="lnk" data-info="wind:_">계산 방법</button></div>
        ${S.wind ? gauge(v) : ""}
        <div class="wnow"><span class="big num" style="color:${z.color}">${v ?? "—"}</span><div><span class="pill" style="background:${z.color}">${z.name}</span><div class="wact">지금은 <b>${z.act}</b></div>
          <div class="note" style="margin-top:2px">${v0 != null && v != null ? `1주 전 ${v0} → ${v > v0 ? "+" : v < v0 ? "−" : "±"}${n2(Math.abs(v - v0), 1)}` : ""}</div></div></div>
        ${S.wind ? verdictBlock(z, wc) : ""}
        <div class="whead">${esc(wc.headline || autoWindHead(v, v0, i))}</div>
        <div class="wparts">${part(`심리 바람 ${pctW(sentW(i))}%`, sent, "#f59e6b", "트렌드캐치를 거꾸로: 공포일수록 ↑")}${part(`유동성 바람 ${pctW(1 - sentW(i))}%`, liq, "#0fb9a5", "돈이 넉넉할수록 ↑")}</div></div>
      ${quadrant(i, cm)}</div>
      ${windCards(b, i)}
      ${pointsBlock("핵심 코멘트", asPoints(wc.points).length ? asPoints(wc.points) : autoPts, "wind")}
      ${scenarioBlock(wc.scenarios)}
      ${S.wind ? `<div id="wmean">${windMeaning(z.name)}</div>` : ""}
      <div class="card sec"><h3>풍향계와 지수, 방향이 맞았나</h3>
        <div class="ctl"><div class="seg" id="segWM">${[["same", "같은 날 (눈금 맞춤)"], ["20", "1개월 뒤 수익률"], ["60", "3개월 뒤 수익률"]].map(([k, t]) => `<button data-v="${k}" class="${W === k ? "on" : ""}">${t}</button>`).join("")}</div>
          <div class="seg" id="segW">${[["6m", "6개월"], ["1y", "1년"], ["all", "전체"]].map(([k, t]) => `<button data-v="${k}" class="${S.wrange === k ? "on" : ""}">${t}</button>`).join("")}</div></div>
        <div class="cap" id="wlinecap"></div>
        <div class="chartbox lg"><canvas id="wline"></canvas></div><div class="note" id="wlinen"></div></div>
      <div class="grid g2e sec">
        <div class="card"><h3>${esc(E.lead_title)}</h3><div class="cap">${esc(E.lead_cap)}</div>
          <div class="chartbox"><canvas id="wlead"></canvas></div><div class="leadv" id="wleadn"></div></div>
        <div class="card"><h3>${esc(E.track_title)}</h3><div class="cap">${esc(E.track_cap)}</div>
          <div class="chartbox"><canvas id="wtrack"></canvas></div></div></div>
      ${weightsCard(i)}
      <div class="note">풍향계는 2023-09부터 계산됩니다(트렌드캐치 9개 지표 중 5개 이상이 모이는 시점). 기간이 3년 남짓이라 매일 쌓이면서 검증이 계속됩니다. 과거 관계가 앞으로도 같다는 보장은 없습니다.</div>`;
    $("#view").innerHTML = html;
    bindInfo(); bindGo(); bindQuad(i, cm);
    $("#view").querySelectorAll("[data-jump]").forEach((x) => x.onclick = (e) => { e.stopPropagation(); const t = document.getElementById(x.dataset.jump); if (t) t.scrollIntoView({ behavior: "smooth", block: "start" }); });
    if (!S.wind) return;
    drawWindLine(i);
    const seg = (id, key) => $(id).querySelectorAll("button").forEach((x) => x.onclick = () => { S[key] = x.dataset.v; $(id).querySelectorAll("button").forEach((y) => y.classList.toggle("on", y === x)); drawWindLine(i); });
    seg("#segW", "wrange"); seg("#segWM", "wmode");
    drawWindLead(z, v); drawWindTrack();
  }
  function drawWindLine(i) {
    killChart("wline"); const el = $("#wline"); if (!el) return;
    const E = M.EXPLAIN, mode = S.wmode || "same";
    const n = { "6m": 126, "1y": 252, "all": 99999 }[S.wrange];
    const st = Math.max(idxOf(S.wind.start), i - n + 1), ds = D().slice(st, i + 1);
    const wv = ds.map((_, m) => windAt(st + m));
    const zs = S.wind.zones, bounds = zs.map((z) => z.from).concat([100]);
    const zp = { id: "wz", beforeDraw(ch) { const { ctx, chartArea: a, scales: { y } } = ch; if (!a) return; ctx.save();
      zs.forEach((z, k) => { const t = y.getPixelForValue(bounds[k + 1]), bt = y.getPixelForValue(bounds[k]); ctx.fillStyle = z.color + "1f"; ctx.fillRect(a.left, t, a.right - a.left, bt - t); });
      ctx.restore(); } };
    const wds = { label: "풍향계", data: wv, borderColor: "#f5cf6a", borderWidth: 2.4, pointRadius: 0, yAxisID: "y", spanGaps: true };
    const yW = { min: 0, max: 100, ticks: { color: "#98acd0", stepSize: 25 }, grid: { color: "#3a589066" }, title: { display: true, text: mode === "same" ? "0~100 (같은 눈금)" : "풍향계", color: "#98acd0" } };
    if (mode === "same") {
      const sc = (k) => { const a = ds.map((_, m) => at(k, st + m)), lg = a.map((x) => x == null ? null : Math.log(x)), vv = lg.filter((x) => x != null);
        const lo = Math.min(...vv), hi = Math.max(...vv); return { raw: a, v: lg.map((x) => x == null ? null : hi > lo ? (x - lo) / (hi - lo) * 100 : 50) }; };
      const sp = sc("spx"), nq = sc("ndx");
      charts.wline = new Chart(el, { type: "line", plugins: [zp],
        data: { labels: ds, datasets: [wds,
          { label: "S&P500 (기간 최저 0 · 최고 100)", data: sp.v, raw: sp.raw, borderColor: "#e8eef8", borderWidth: 1.4, pointRadius: 0, yAxisID: "y", spanGaps: true },
          { label: "나스닥100 (기간 최저 0 · 최고 100)", data: nq.v, raw: nq.raw, borderColor: "#7cb7ff", borderWidth: 1.4, pointRadius: 0, yAxisID: "y", spanGaps: true }] },
        options: { maintainAspectRatio: false, interaction: { mode: "index", intersect: false },
          plugins: { legend: { labels: { color: "#dfe7f7", boxWidth: 12 } }, tooltip: { callbacks: { label: (c) => c.datasetIndex === 0 ? ` 풍향계 ${c.raw} (${zoneOf(c.raw).name})` : ` ${c.dataset.label.split(" ")[0]} ${n2(c.dataset.raw[c.dataIndex], 2)} (눈금 ${n2(c.raw, 0)})` } } },
          scales: { x: axisX(7), y: yW } } });
      $("#wlinecap").textContent = "금색 = 풍향계 · 흰색·파랑 = S&P500·나스닥100을 같은 0~100 눈금으로 바꾼 것 (배경색 = 풍향계 구간)";
      $("#wlinen").textContent = E.same_scale;
      return;
    }
    const h = +mode, hn = h === 20 ? "1개월" : "3개월", px = C("spx"), last = D().length - 1;
    const fwd = ds.map((_, m) => { const k = st + m, a = px[k], b = k + h <= last ? px[k + h] : null; return a != null && b != null ? +((b / a - 1) * 100).toFixed(2) : null; });
    const R = Math.max(5, Math.ceil(Math.max(...fwd.filter((x) => x != null).map(Math.abs), 0) / 5) * 5);
    const mid = hlinePlugin([[50, "", "#cbd5e1"]]);
    charts.wline = new Chart(el, { type: "line", plugins: [zp, mid],
      data: { labels: ds, datasets: [wds,
        { label: `S&P500 ${hn} 뒤 수익률`, data: fwd, borderColor: "#e8eef8", borderWidth: 1.6, pointRadius: 0, yAxisID: "y2", spanGaps: false }] },
      options: { maintainAspectRatio: false, interaction: { mode: "index", intersect: false },
        plugins: { legend: { labels: { color: "#dfe7f7", boxWidth: 12 } }, tooltip: { callbacks: { label: (c) => c.datasetIndex === 0 ? ` 풍향계 ${c.raw} (${zoneOf(c.raw).name})` : ` 이날 샀다면 ${hn} 뒤 ${sgn(c.raw, 1, "%")}` } } },
        scales: { x: axisX(7), y: yW, y2: { position: "right", min: -R, max: R, ticks: { color: "#98acd0", callback: (x) => x + "%" }, grid: { display: false }, title: { display: true, text: `${hn} 뒤 수익률`, color: "#98acd0" } } } } });
    const ic = rankCorr(wv, fwd);
    $("#wlinecap").textContent = `금색 = 풍향계(왼쪽) · 흰색 = 그날 S&P500을 샀다면 ${hn} 뒤 수익률(오른쪽) · 가운데 점선 = 풍향계 50 / 수익률 0%`;
    $("#wlinen").textContent = E.forward.split("{h}").join(hn) + (ic == null ? "" : ` 이 화면 기간의 같은 방향 정도: ${ic > 0 ? "+" : ""}${ic.toFixed(2)} (${icWords(ic)}${ic < 0 ? ", 반대 방향" : ""}).`);
  }
  function drawWindLead(z, v) {
    killChart("wlead"); const el = $("#wlead"); if (!el) return;
    const L = S.wind.lead, hs = ["5", "10", "20", "40", "60"];
    charts.wlead = new Chart(el, { type: "bar",
      data: { labels: hs.map((h) => S.wind.hname[h] + " 뒤"), datasets: [
        { label: "S&P500", data: hs.map((h) => L.spx.fwd[h]), backgroundColor: "#e8eef8", borderRadius: 4 },
        { label: "나스닥100", data: hs.map((h) => L.ndx.fwd[h]), backgroundColor: "#7cb7ff", borderRadius: 4 }] },
      options: { maintainAspectRatio: false, plugins: { legend: { labels: { color: "#dfe7f7", boxWidth: 12 } }, tooltip: { callbacks: { label: (c) => ` ${c.dataset.label} ${c.raw > 0 ? "+" : ""}${c.raw} (${icWords(c.raw)})` } } },
        scales: { x: { ticks: { color: "#dfe7f7" }, grid: { display: false } }, y: { min: -0.2, max: 0.6, ticks: { color: "#98acd0", stepSize: 0.2, callback: (x) => (x > 0 ? "+" : "") + x.toFixed(1) }, grid: { color: "#3a589066" }, title: { display: true, text: "맞힌 정도", color: "#98acd0" } } } } });
    const f = (x) => (x > 0 ? "+" : "") + x.toFixed(2);
    const st60 = (S.wind.stats.spx["60"] || {})[z.name];
    $("#wleadn").innerHTML = `<div><b>한 줄 요약</b>풍향계는 바로 다음 주보다 <b>1~3개월 뒤</b>를 더 잘 맞혔습니다. S&P500 기준 1주 뒤 ${f(L.spx.fwd["5"])}(${icWords(L.spx.fwd["5"])}) → 3개월 뒤 ${f(L.spx.fwd["60"])}(${icWords(L.spx.fwd["60"])}), 나스닥100 3개월 뒤 ${f(L.ndx.fwd["60"])}(${icWords(L.ndx.fwd["60"])}).</div>
      ${st60 && v != null ? `<div><b>지금에 대입하면</b>풍향계 ${v}(${z.name})와 같은 구간이었던 ${st60.n}일 동안, 3개월 뒤 S&P500은 평균 ${sgn(st60.mean, 1, "%")}였고 ${n2(st60.win, 0)}%의 경우 올랐습니다.</div>` : ""}
      <div><b>왜 같은 날엔 반대로 보이나</b>주가가 많이 빠진 뒤에 풍향계가 올라가는 구조라, 지난 3개월 수익률과는 ${f(L.spx.past["60"])}로 반대 방향입니다. 그래서 같은 날 그래프에서는 지수와 엇갈려 보입니다. 표본 ${L.spx.n["60"]}거래일.</div>`;
  }
  function drawWindTrack() {
    killChart("wtrack"); const el = $("#wtrack"); if (!el) return;
    const t = S.wind.track;
    charts.wtrack = new Chart(el, { type: "line", plugins: [hlinePlugin([[0, "0 = 못 맞힘", "#8ea3cc"]])],
      data: { labels: t.spx.dates, datasets: [
        { label: "S&P500", data: t.spx["60"], borderColor: "#e8eef8", borderWidth: 1.6, pointRadius: 0, spanGaps: true },
        { label: "나스닥100", data: t.ndx["60"], borderColor: "#7cb7ff", borderWidth: 1.6, pointRadius: 0, spanGaps: true }] },
      options: { maintainAspectRatio: false, plugins: { legend: { labels: { color: "#dfe7f7", boxWidth: 12 } }, tooltip: { callbacks: { label: (c) => c.raw == null ? null : ` ${c.dataset.label} ${c.raw > 0 ? "+" : ""}${c.raw} (${icWords(c.raw)})` } } },
        scales: { x: axisX(5), y: { min: -0.6, max: 0.8, ticks: { color: "#98acd0", stepSize: 0.2 }, grid: { color: "#3a589066" } } } } });
  }

  // ---------------------------------------------------------------- 증시현황판
  const descOf = (r) => r.desc || (S.notes[r.t] && S.notes[r.t].desc) || `${r.name}${r.ind ? " · " + indKo(r.ind) : ""}`;
  function autoCards(b, i) {
    const out = [], ix = (k) => { const p = lastN(k, i, 2); return p.length < 2 ? null : (p[1].v / p[0].v - 1) * 100; };
    const spx = ix("spx"), ndx = ix("ndx"), tone = (x, th = 0.25) => x == null ? "flat" : Math.abs(x) < th ? "flat" : x > 0 ? "up" : "down";
    out.push({ tone: tone(spx), tag: "지수", title: `S&P500 ${sgn(spx, 2, "%")}, 나스닥100 ${sgn(ndx, 2, "%")}`, num: `VIX ${n2(at("vix", i), 1)}`, back: `S&P500 ${n2(at("spx", i), 2)}, 나스닥100 ${n2(at("ndx", i), 2)}로 마감했습니다.` });
    const br = b.breadth;
    out.push({ tone: br.nh >= br.nl * 1.5 ? "up" : br.nl >= br.nh * 1.5 ? "down" : "flat", tag: "시장 체력", title: br.nl > br.nh ? "신저가가 신고가보다 많음" : "신고가가 신저가보다 많음", num: `신고가 ${br.nh} · 신저가 ${br.nl}`,
      back: `오른 종목 ${br.adv.toLocaleString()}개, 내린 종목 ${br.dec.toLocaleString()}개. 미국 전체 200일선 위 ${n2(br.above200, 1)}%, S&P500 200일선 위 ${n2(br.sp500_above200, 1)}%.` });
    const sp = b.sector_perf || [];
    if (sp.length) {
      const hi = sp[0], lo = sp[sp.length - 1];
      out.push({ tone: hi.chg > 0 ? "up" : "flat", tag: "강한 섹터", title: `${hi.name} 강세`, num: sgn(hi.chg, 2, "%"), back: `섹터 1~3위: ${sp.slice(0, 3).map((s) => `${s.name} ${sgn(s.chg, 2, "%")}`).join(", ")}.` });
      out.push({ tone: lo.chg < 0 ? "down" : "flat", tag: "약한 섹터", title: `${lo.name} 약세`, num: sgn(lo.chg, 2, "%"), back: `가장 약한 섹터: ${sp.slice(-3).reverse().map((s) => `${s.name} ${sgn(s.chg, 2, "%")}`).join(", ")}.` });
    }
    return out;
  }
  function marketBlock(b, cm, i) {
    const mk = cm.market || {}, cards = (mk.cards && mk.cards.length) ? mk.cards : autoCards(b, i);
    const TN = { up: "좋은 소식", down: "나쁜 소식", flat: "엇갈림" };
    return `<div class="card sec mkt"><div class="mh"><h3>시장의 변화</h3><button class="lnk" data-info="board:market">읽는 법</button>
        <span class="mlg"><i class="g"></i>좋은 소식 <i class="r"></i>나쁜 소식 <i class="n"></i>엇갈림 · 카드를 누르면 뒤집혀요</span></div>
      ${mk.headline ? `<div class="mhead">${esc(mk.headline)}</div>` : ""}
      <div class="mcards">${cards.map((c) => `<div class="mc t-${c.tone || "flat"}" tabindex="0" role="button" aria-label="${esc(c.title)} 자세히 보기"><div class="in">
        <div class="fr"><span class="tg">${esc(c.tag || "")}<em>${TN[c.tone || "flat"]}</em></span><div class="tt">${esc(c.title)}</div>${c.num ? `<div class="nm num">${esc(c.num)}</div>` : ""}<span class="hint">눌러서 자세히 ↻</span></div>
        <div class="bk"><div class="tt2">${esc(c.title)}</div><p>${esc(c.back || "")}</p><span class="hint">다시 누르면 앞면 ↻</span></div></div></div>`).join("")}</div></div>`;
  }
  function bindCards() {
    $("#view").querySelectorAll(".mc").forEach((c) => { const f = () => c.classList.toggle("flip"); c.onclick = f; c.onkeydown = (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); f(); } }; });
  }
  function indexCards(i) {
    const mk = (k, nm, goodUp, dec, big, unit = "") => {
      const p = lastN(k, i, 6); if (p.length < 2) return `<div class="card ${big ? "" : "mini"}">${nm} —</div>`;
      const last = p[p.length - 1].v, prev = p[p.length - 2].v;
      const isY = k === "us10y", chg = isY ? (last - prev) * 100 : (last / prev - 1) * 100;
      const good = chg === 0 ? null : (goodUp ? chg > 0 : chg < 0), cc = good == null ? "flat" : good ? "up" : "down";
      const ct = isY ? sgn(chg, 0, "bp") : sgn(chg, 2, "%");
      const fmt = (x) => n2(x, dec) + unit;
      if (big) return `<div class="card click" data-info="board:index"><div class="idx"><span class="nm">${nm}</span><span class="pct num ${cc}">${ct}</span></div><div class="cl num">${fmt(last)}</div>${idxChart(p, goodUp, fmt)}</div>`;
      return `<div class="card mini click" data-info="board:index"><span class="nm">${nm}</span><span class="v num">${fmt(last)} <small class="${cc}">${ct}</small></span>${idxChart(p, goodUp, fmt)}</div>`;
    };
    return `<div class="grid g3">${mk("spx", "S&P500", true, 2, true)}${mk("ixic", "나스닥 종합", true, 2, true)}${mk("dji", "다우존스", true, 2, true)}</div>
      <div class="grid g5 sec">${mk("ndx", "나스닥100", true, 2)}${mk("kospi", "코스피", true, 2)}${mk("vix", "VIX 공포지수", false, 2)}${mk("dxy", "달러인덱스", false, 2)}${mk("us10y", "미 10년물 금리", false, 2, false, "%")}</div>`;
  }
  function breadthCard(b) {
    const br = b.breadth, pv = b.prev;
    const grp = (title, rows) => `<tr class="grp"><td colspan="4">${title}</td></tr>` + rows.map(([k, nm, pct, good]) => {
      const now = br[k], was = pv ? pv[k] : null, ch = was == null || now == null ? null : now - was;
      const fmt = (v) => v == null ? "—" : pct ? n2(v, 1) + "%" : Number(v).toLocaleString();
      const chs = ch == null ? "—" : (pct ? sgn(ch, 1, "%p") : (ch > 0 ? "+" : ch < 0 ? "−" : "") + Math.abs(ch).toLocaleString());
      return `<tr class="click" data-info="board:${k}"><td>${nm}</td><td class="num">${fmt(was)}</td><td class="num now">${fmt(now)}</td><td class="num ${ch == null ? "flat" : ch * good > 0 ? "up" : ch * good < 0 ? "down" : "flat"}">${chs}</td></tr>`;
    }).join("");
    return `<div class="card"><h3>시장 체력 (Breadth)</h3>
      <div class="cap"><b>기준</b> 미국 상장 주식 ${br.universe.toLocaleString()}종목(ETF 제외)과 S&P500 503종목 · ${short(b.date)} 종가 · 항목을 누르면 설명</div>
      <table class="bt"><tr><th>항목</th><th>${pv ? short(pv.date) : "전날"}</th><th>${short(b.date)}</th><th>변화</th></tr>
        ${grp(`미국 전체 ${br.universe.toLocaleString()}종목`, [["adv", "오른 종목", 0, 1], ["dec", "내린 종목", 0, -1], ["nh", "52주 신고가", 0, 1], ["nl", "52주 신저가", 0, -1], ["above50", "50일선 위", 1, 1], ["above200", "200일선 위", 1, 1]])}
        ${grp("S&P500 503종목", [["sp500_above50", "50일선 위", 1, 1], ["sp500_above200", "200일선 위", 1, 1]])}</table>
      ${pv ? "" : `<div class="note">전날 칸은 다음 거래일부터 채워집니다.</div>`}</div>`;
  }
  async function drawBreadth(i) {
    killChart("bline"); const el = $("#bline"); if (!el) return;
    if (!S.hist) { const [bh, a2, a5] = await Promise.all([getJSON("data/hist/breadth.json").catch(() => ({})), getJSON("data/hist/sp500_a200.json").catch(() => ({})), getJSON("data/hist/sp500_a50.json").catch(() => ({}))]); S.hist = { bh, a2, a5 }; }
    if (!$("#bline")) return;
    const end = D()[i], days = { "6m": 183, "1y": 366, "3y": 1096 }[S.brange];
    const sd = new Date(new Date(end + "T00:00:00").getTime() - days * 864e5).toISOString().slice(0, 10);
    const set = new Set(Object.keys(S.hist.a2).concat(Object.keys(S.hist.a5), Object.keys(S.hist.bh)).filter((d) => d >= sd && d <= end));
    const ds = [...set].sort(), bh = S.hist.bh;
    const few = (arr) => arr.filter((x) => x != null).length < 15;
    const mkDs = (label, data, col, dash) => ({ label, data, borderColor: col, backgroundColor: col, borderWidth: 2, borderDash: dash || [], pointRadius: few(data) ? 4 : 0, spanGaps: true });
    const sp200 = ds.map((d) => S.hist.a2[d] ?? null), sp50 = ds.map((d) => S.hist.a5[d] ?? bh[d]?.sp500_above50 ?? null), al200 = ds.map((d) => bh[d]?.above200 ?? null), al50 = ds.map((d) => bh[d]?.above50 ?? null);
    charts.bline = new Chart(el, { type: "line", plugins: [hlinePlugin([[80, "80% 과열권", "#f59e6b"], [50, "50%", "#8ea3cc"], [20, "20% 바닥권", "#5fd3b0"]])],
      data: { labels: ds, datasets: [mkDs("S&P500 200일선 위", sp200, "#f5cf6a"), mkDs("S&P500 50일선 위", sp50, "#0fb9a5"), mkDs("미국 전체 200일선 위", al200, "#e8eef8", [5, 4]), mkDs("미국 전체 50일선 위", al50, "#c084fc", [5, 4])] },
      options: { maintainAspectRatio: false, interaction: { mode: "index", intersect: false },
        plugins: { legend: { labels: { color: "#dfe7f7", boxWidth: 12, font: { size: 12 } } }, tooltip: { callbacks: { label: (c) => c.raw == null ? null : ` ${c.dataset.label} ${n2(c.raw, 1)}%` } } },
        scales: { x: axisX(7), y: { min: 0, max: 100, ticks: { color: "#98acd0", stepSize: 20, callback: (v) => v + "%" }, grid: { color: "#3a589066" } } } } });
  }
  function industryBlock(b) {
    const top = b.ind_top || [], bot = b.ind_bottom || []; if (!top.length) return "";
    const mx = Math.max(...top.concat(bot).map((x) => Math.abs(x.chg || 0)), 0.5);
    const row = (x, good) => `<div class="ir"><div class="inm"><b>${esc(indKo(x.name))}</b><span>${esc(x.sector)} · ${x.n}종목</span></div>
      <div class="ibar"><i style="width:${Math.abs(x.chg) / mx * 100}%;background:${good ? GOOD : BAD}"></i></div><span class="iv num ${cls(x.chg)}">${sgn(x.chg, 2, "%")}</span>
      ${x.tops ? `<div class="itk">${x.tops.map((t) => `<span>${t.t} <em class="${cls(t.chg)}">${sgn(t.chg, 1, "%")}</em></span>`).join("")}</div>` : ""}</div>`;
    return `<div class="card sec click" data-info="board:industries"><h3>강한 산업 · 약한 산업</h3><div class="cap">약 145개 세부 산업 중 오늘 가장 강했던 5개와 약했던 5개 · 시가총액 가중 · 아래 티커 = 그 산업 시총 상위 3종목</div>
      <div class="indg"><div class="indb good"><div class="ih">▲ 강한 산업</div>${top.map((x) => row(x, true)).join("")}</div>
        <div class="indb bad"><div class="ih">▼ 약한 산업</div>${bot.map((x) => row(x, false)).join("")}</div></div></div>`;
  }
  function t40Body(b) {
    const { k, dir } = S.t40, arr = b.top40.map((r, n) => Object.assign({ rank: n + 1 }, r));
    arr.sort((a, c) => { const x = a[k], y = c[k]; if (typeof x === "string" || typeof y === "string") return dir * String(x || "").localeCompare(String(y || ""), "ko"); return dir * ((x ?? -1e15) - (y ?? -1e15)); });
    return arr.map((r) => `<tr><td class="r muted">${r.rank}</td><td class="t">${r.t}${r.sp ? '<span class="badge-sp">S&P</span>' : ""}</td><td class="ds">${esc(descOf(r))}</td><td class="hs">${esc(r.sector)}</td><td class="r num hs2">$${r.mcap >= 1000 ? n2(r.mcap / 1000, 1) + "B" : n2(r.mcap, 0) + "M"}</td><td class="r ${cls(r.chg)} num">${sgn(r.chg, 2, "%")}</td></tr>`).join("");
  }
  function t40Head() {
    const th = (key, label, extra = "") => { const on = S.t40.k === key; return `<th class="${extra} sortable ${on ? "on" : ""}" data-sort="${key}">${label}<i>${on ? (S.t40.dir > 0 ? "▲" : "▼") : "↕"}</i></th>`; };
    return `<tr><th class="r">#</th>${th("t", "티커")}<th>무슨 회사</th>${th("sector", "섹터", "hs")}${th("mcap", "시총", "r hs2")}${th("chg", "등락", "r")}</tr>`;
  }
  function bindT40(b) {
    const tb = $("#t40"); if (!tb) return;
    const bind = () => tb.querySelectorAll("th[data-sort]").forEach((th) => th.onclick = () => {
      const key = th.dataset.sort;
      if (S.t40.k === key) S.t40.dir *= -1; else { S.t40.k = key; S.t40.dir = (key === "t" || key === "sector") ? 1 : -1; }
      tb.innerHTML = t40Head() + t40Body(b); bind();
    });
    bind();
  }
  async function viewBoard() {
    const i = idxOf(S.date), d = D()[i];
    const b = await board(d), cm = (await comments(d)) || {};
    let html = indexCards(i);
    if (!b) {
      html += `<div class="empty sec">${S.latest.boards.length ? `현황판(시장의 변화·Breadth·섹터·신고가) 기록은 ${S.latest.boards[0]}부터 쌓이고 있습니다.` : "아직 현황판 기록이 없습니다."}<br>
        이 날짜의 풍향계·트렌드캐치·유동성은 위 탭에서 볼 수 있습니다.</div>`;
      $("#view").innerHTML = html; bindInfo(); return;
    }
    html += marketBlock(b, cm, i);
    const sp = b.sector_perf || [], gn = b.gainers || [];
    html += `<div class="grid g2 sec">${breadthCard(b)}
      <div class="card click" data-info="board:sectors"><h3>섹터 강도</h3><div class="cap">11개 섹터의 시가총액 가중 등락률 · 괄호 = 오른 종목 비율</div>
        <div class="chartbox" style="height:${Math.max(240, sp.length * 28)}px"><canvas id="secbar"></canvas></div></div></div>
      <div class="card sec"><div class="mh"><h3>200일선 · 50일선 위 종목 비율</h3><button class="lnk" data-info="board:bchart">읽는 법</button></div>
        <div class="cap">주가가 이동평균선 위에 있는 종목의 비율 · <b>S&P500 200일선·50일선</b>은 2017년부터(구성종목 일봉으로 직접 계산), <b>미국 전체</b>는 2026-11-13부터 매일 쌓임 · 참고: barchart의 미국 전체 50일선 비율(<a href="https://www.barchart.com/stocks/quotes/$MMFI/technical-chart" target="_blank" rel="noopener">$MMFI</a>)·200일선 비율(<a href="https://www.barchart.com/stocks/quotes/$MMTH/technical-chart" target="_blank" rel="noopener">$MMTH</a>)은 대상 종목 범위가 달라 값이 다릅니다</div>
        <div class="ctl"><div class="seg" id="segB">${[["6m", "6개월"], ["1y", "1년"], ["3y", "3년"]].map(([k, t]) => `<button data-v="${k}" class="${S.brange === k ? "on" : ""}">${t}</button>`).join("")}</div></div>
        <div class="chartbox lg"><canvas id="bline"></canvas></div></div>`;
    html += industryBlock(b);
    // 강세주 + 신고가 업종 분포
    const stRow = (r, n) => `<tr><td class="r muted">${n}</td><td class="t">${r.t}</td><td class="ds">${esc(descOf(r))}</td><td class="r ${cls(r.chg)} num">${sgn(r.chg, 2, "%")}</td></tr>`;
    const top = b.top40.length, nl = b.nh_list || b.top40.map((r) => ({ t: r.t, chg: r.chg, sp: r.sp }));
    const leg = b.sectors.map((s) => `<div class="row"><span class="sw" style="background:${SECTOR_COL[s.name] || "#64748b"}"></span>${esc(s.name)}<span class="ct num">${s.count}개 ${n2(s.pct, 1)}%</span></div>`).join("");
    html += `<div class="grid g2 sec">
      <div class="card click" data-info="board:gainers"><h3>강세주 · 약세주 (S&P500)</h3><div class="cap">S&P500 구성종목 오늘 등락률 상위 10 · 하위 5</div>
        <table class="st">${gn.map((r, n) => stRow(r, n + 1)).join("")}</table>
        <div class="cap" style="margin:10px 0 2px">약세 5</div><table class="st">${(b.losers || []).map((r, n) => stRow(r, n + 1)).join("")}</table>
        <div class="cap" style="margin:10px 0 2px">시가총액 상위 10</div><div class="mchips">${(b.mega || []).map((r) => `<span><b>${r.t}</b> <span class="${cls(r.chg)}">${sgn(r.chg, 2, "%")}</span></span>`).join("")}</div></div>
      <div class="card"><h3 class="click" data-info="board:top40">신고가 TOP${top} 업종 분포</h3><div class="cap">오늘 52주 신고가 ${b.nh_total}개 중 우선주·SPAC 제외, 시가총액 상위 ${top}개</div>
        <div class="donut"><div class="cv"><canvas id="donut"></canvas><div class="ctr"><b>${top}개</b><span>섹터별</span></div></div><div class="legend">${leg}</div></div>
        <div class="cap" style="margin:14px 0 4px">오늘 신고가 종목 전체 ${nl.length}개 <span class="muted">· 굵은 글씨 = S&P500 · 시가총액 순</span></div>
        <div class="tkr">${nl.map((r) => `<span class="${r.sp ? "sp" : ""}">${r.t}<em class="${cls(r.chg)}">${sgn(r.chg, 1, "%")}</em></span>`).join("")}</div></div></div>`;
    // 대표 신고가 (S&P500)
    const F = cm.features || {};
    const cards = b.features.map((f) => {
      const c = F[f.t], sk = f.spark || [], r3 = sk.length > 1 ? (sk[sk.length - 1] / sk[0] - 1) * 100 : null;
      const body = c ? `<div><div class="k">무슨 회사 (BM)</div>${esc(c.bm)}</div><div class="hr"></div>
          <div><div class="k2">최근 실적·신고가 배경</div>${esc(c.e1)}<br><span class="sub">${esc(c.e2 || "")}</span></div><div class="hr"></div>
          <div class="pt"><b>포인트</b>${esc(c.point)}</div><div class="ct"><b>주의</b>${esc(c.caution)}</div>`
        : `<div class="pend">코멘트 준비 중</div><div class="sub">${esc(descOf(f))} · 시총 $${n2(f.mcap / 1000, 1)}B</div>`;
      return `<div class="fc"><div class="top"><span>${f.t}</span><span class="${cls(f.chg)} num">${sgn(f.chg, 2, "%")}</span></div>
        ${sk.length > 1 ? `<div class="fsp">${spark(sk, (r3 ?? 0) >= 0 ? GOOD : BAD)}<span>3개월 <b class="${cls(r3)}">${sgn(r3, 1, "%")}</b></span></div>` : ""}
        <div class="bd">${body}</div></div>`;
    }).join("");
    html += `<div class="sec"><div class="mh" style="margin:6px 2px 8px"><h3 style="margin:0;color:var(--gold);font-size:18px">대표 신고가 ${b.features.length}선 (S&P500)</h3>
      <button class="lnk" data-info="board:features">선정 기준</button></div>
      ${b.features.length ? `<div class="grid g3f">${cards}</div>` : `<div class="empty">이날 S&P500 종목 중 52주 신고가가 없었습니다.</div>`}</div>`;
    // 신고가 TOP40 표
    html += `<div class="card sec"><h3>신고가 TOP${top} 종목</h3><div class="cap">제목(티커·섹터·시총·등락)을 누르면 오름차순·내림차순으로 정렬 · S&P = S&P500 구성종목 · 회사 설명은 Claude 작성</div>
      <table class="st" id="t40">${t40Head()}${t40Body(b)}</table></div>
      <div class="note">미국 ${short(b.date)} 정규장 기준 · 실적은 그날 상승의 단일 원인으로 단정하지 않음 · 생성 ${esc(b.generated)}</div>`;
    $("#view").innerHTML = html;
    killChart("donut"); killChart("secbar");
    charts.donut = new Chart($("#donut"), { type: "doughnut",
      data: { labels: b.sectors.map((s) => s.name), datasets: [{ data: b.sectors.map((s) => s.count), backgroundColor: b.sectors.map((s) => SECTOR_COL[s.name] || "#64748b"), borderColor: "#243b69", borderWidth: 2 }] },
      options: { cutout: "58%", plugins: { legend: { display: false }, tooltip: { callbacks: { label: (c) => ` ${c.label} ${c.raw}개` } } }, maintainAspectRatio: false } });
    if (sp.length) charts.secbar = new Chart($("#secbar"), { type: "bar",
      data: { labels: sp.map((s) => `${s.name} (${s.up_pct}%)`), datasets: [{ data: sp.map((s) => s.chg), backgroundColor: sp.map((s) => s.chg >= 0 ? GOOD : BAD), borderRadius: 4 }] },
      options: { indexAxis: "y", maintainAspectRatio: false, plugins: { legend: { display: false }, tooltip: { callbacks: { label: (c) => ` ${sgn(c.raw, 2, "%")}` } } },
        scales: { x: { ticks: { color: "#98acd0", callback: (v) => v + "%" }, grid: { color: "#3a5890" } }, y: { ticks: { color: "#f5f8ff", font: { size: 13 } }, grid: { display: false } } } } });
    $("#segB").querySelectorAll("button").forEach((x) => x.onclick = () => { S.brange = x.dataset.v; $("#segB").querySelectorAll("button").forEach((y) => y.classList.toggle("on", y === x)); drawBreadth(i); });
    drawBreadth(i); bindCards(); bindT40(b); bindInfo();
  }

  // ---------------------------------------------------------------- 트렌드캐치·유동성 공통
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
        <div class="f">${s ? `<span class="pill" style="background:${col(s)}">${s} ${L[s]}</span>` : pill(null)}<span>${kind === "lq" ? `<span class="w">${fmtW(wOf("lq", m.key, i))}% · </span>` : ""}1주 전 ${arrow || "—"}</span></div></div>`;
    }).join("");
  }
  function autoOpinion(kind, i) {
    const v = at(kind, i), v0 = at(kind, i - 5); if (v == null) return "";
    const lab = kind === "tc" ? labelTC(v) : labelLQ(v);
    const mv = v0 == null ? "" : v > v0 ? ` 1주 전(${v0})보다 올랐습니다.` : v < v0 ? ` 1주 전(${v0})보다 내렸습니다.` : " 1주 전과 같습니다.";
    return kind === "tc" ? `${v} ${lab}: '${M.TC_ACTION[lab]}' 구간입니다.${mv}` : `${v} ${lab}: 주식에 ${M.LQ_STANCE[lab]}입니다.${mv}`;
  }
  function compositeCard(kind, i, cm) {
    const v = at(kind, i), lab = kind === "tc" ? labelTC(v) : labelLQ(v), col = kind === "tc" ? colTC(lab) : colLQ(lab);
    const j = i - 5, v0 = at(kind, j), Z = kind === "tc" ? TC_Z : LQ_Z, CC = kind === "tc" ? TCC : LQC;
    const act = kind === "tc" ? M.TC_ACTION[lab] : M.LQ_STANCE[lab];
    const pos = v == null ? null : Math.max(0, Math.min(100, (v - 1) / 4 * 100));
    const cov = kind === "tc" ? `9개 중 ${at("tc_n", i) ?? 0}개 지표로 계산` : `가중치 ${n2(at("lq_w", i), 1)}% 반영`;
    const op = (cm && (kind === "tc" ? cm.tc_summary : cm.lq_summary)) || autoOpinion(kind, i);
    return `<div class="card"><h3 class="${kind}h click" data-info="${kind}:_comp">${kind === "tc" ? "트렌드캐치" : "유동성"} 종합 · ${short(D()[i])}</h3>
      <div class="click" data-info="${kind}:_comp"><div style="display:flex;align-items:center;gap:12px;margin-top:8px"><span class="big num" style="color:${col}">${v ?? "—"}</span>
        <div>${pill(lab, col)}<div style="margin-top:4px;font-size:15px">${act ? (kind === "tc" ? "매매 판단: " : "주식에: ") + `<b>${act}</b>` : ""}</div></div></div>
      <div class="scale">${CC.map((c) => `<div style="background:${c}"></div>`).join("")}</div>
      <div class="marker">${pos == null ? "" : `<i style="left:${pos}%"></i>`}</div>
      <div class="scalelb">${Z.map((z) => `<span>${z}</span>`).join("")}</div>
      <div class="note">${v0 != null && v != null ? `1주 전 ${v0} → ${v > v0 ? "+" : ""}${(v - v0).toFixed(1)}` : ""} · ${cov}</div></div>
      <div class="cap" style="margin:14px 0 4px">최근 3개월 추이</div><div class="chartbox" style="height:150px"><canvas id="cmini"></canvas></div>
      ${op ? `<div class="opinion ${kind}"><b>종합의견</b>${esc(op)}</div>` : ""}</div>`;
  }
  function heatmap(kind, list, i) {
    const cols = weekEnds(i, 12), p = kind === "tc" ? "s_tc_" : "s_lq_", CC = kind === "tc" ? TCC : LQC;
    const head = `<div></div>` + cols.map((k) => `<div class="hd">${short(D()[k])}</div>`).join("");
    const row = (nm, key, comp) => `<div class="rl">${nm}</div>` + cols.map((k) => {
      const v = comp ? at(kind, k) : at(p + key, k);
      if (v == null) return `<div class="cl na ${k === i ? "sel" : ""}" data-d="${D()[k]}">·</div>`;
      const s = comp ? Math.min(5, Math.max(1, Math.round(v))) : v;
      return `<div class="cl ${k === i ? "sel" : ""}" data-d="${D()[k]}" style="background:${CC[s - 1]}" title="${nm} ${D()[k]}: ${v}">${v}</div>`;
    }).join("");
    return `<div class="card"><h3 class="${kind}h">지표별 점수 히트맵</h3><div class="cap">주 마지막 거래일 기준 최근 12주 · 칸을 누르면 그 날짜로 이동 · ${kind === "tc" ? "파랑 = 공포, 빨강 = 광기" : "갈색 = 경색, 청록 = 풍부"}</div>
      <div class="hmwrap"><div class="hm" style="grid-template-columns:96px repeat(${cols.length},minmax(30px,1fr))">${head}${list.map((m) => row(m.short || m.name, m.key)).join("")}${row("종합", null, true)}</div></div></div>`;
  }
  const H_NAME = { "1": "1주 뒤", "4": "4주(약 1개월) 뒤", "12": "12주(약 3개월) 뒤" };
  const icWord = (ic) => ic == null ? "자료 없음" : Math.abs(ic) < 0.1 ? "관계 거의 없음" : (ic < 0 ? "점수 높을수록 그 뒤 수익 낮음" : "점수 높을수록 그 뒤 수익 높음") + ` (${icWords(ic)})`;
  function corrBlock(kind) {
    const E = M.EXPLAIN, nm = kind === "tc" ? "트렌드캐치" : "유동성";
    return `<div class="card sec"><h3 class="${kind}h">${esc(E.corr_title)}</h3>
      <div class="cap">${esc(E.corr_intro.split("{name}").join(nm))}</div>
      <div class="ctl"><div class="seg" id="segH">${["1", "4", "12"].map((h) => `<button data-v="${h}" class="${S.h === h ? "on" : ""}">${H_NAME[h]}</button>`).join("")}</div>
        <div class="seg" id="segIdx">${Object.entries(IDX_NAME).map(([k, v]) => `<button data-v="${k}" class="${S.idx === k ? "on" : ""}">${v}</button>`).join("")}</div>
        <div class="seg" id="segR">${[["1y", "1년"], ["3y", "3년"]].map(([k, v]) => `<button data-v="${k}" class="${S.range === k ? "on" : ""}">${v}</button>`).join("")}</div></div>
      <div class="cnow ${kind}" id="cnow"></div>
      <div class="grid g2e"><div><div class="ctitle" id="cbt"></div><div class="chartbox"><canvas id="cbar"></canvas></div><div class="note" id="cnote"></div></div>
        <div><div class="ctitle">세 지수별 '맞힌 정도' <small>(누르면 그 지수로 바뀜)</small></div><div class="cstat" id="cstat"></div>
          <div class="note">${esc(E.corr_sign)}</div>
          <div class="ctitle" style="margin-top:10px">점수(왼쪽 축)와 <span id="clname"></span>(오른쪽 축) 흐름</div><div class="chartbox sm"><canvas id="cline"></canvas></div>
          <div class="ctitle" style="margin-top:10px">시기마다 관계가 같았나 <small>(최근 26주씩 끊어서 · 점수 vs 4주 뒤 수익률)</small></div><div class="chartbox sm"><canvas id="croll"></canvas></div><div class="note">${esc(E.corr_roll)}</div></div></div>
      <div class="note">${kind === "tc" ? "트렌드캐치 과거값은 웹에서 확인하는 4개 지표(F&G·AAII·풋콜·신용융자)의 과거 기록이 부족해 대부분 5~6개 지표로 계산됐습니다. 매일 쌓이면서 정확해집니다." : "유동성은 신용융자 과거 기록이 부족한 기간은 나머지 지표 가중치로 다시 나눠 계산했습니다."} 코스피는 미국 t일 다음 한국 거래일 종가로 맞췄습니다. 과거 관계가 앞으로도 같다는 보장은 없습니다.</div></div>`;
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
    const Z = kind === "tc" ? TC_Z : LQ_Z, CC = kind === "tc" ? TCC : LQC, nm = kind === "tc" ? "트렌드캐치" : "유동성";
    const all = S.corr && S.corr[kind], cr = all && all[S.idx];
    killChart("cbar"); killChart("cline"); killChart("croll");
    if (!cr) return;
    const v = at(kind, i), lab = kind === "tc" ? labelTC(v) : labelLQ(v), bk = cr.buckets[S.h] || {}, hn = H_NAME[S.h], ix = IDX_NAME[S.idx];
    let tn = 0, tm = 0; Object.values(bk).forEach((r) => { tn += r.n; tm += r.mean * r.n; });
    const avg = tn ? tm / tn : null, cb = bk[lab];
    $("#cnow").innerHTML = v == null ? "이 날짜의 점수가 없습니다." : cb
      ? `<b>지금 ${nm} ${v} = '${lab}' 구간</b><div>과거 ${nm}가 '${lab}'였던 <b>${cb.n}주</b> 동안, 그때 ${ix}를 샀다면 <b>${hn}</b> 평균 <b class="num ${cls(cb.mean)}">${sgn(cb.mean, 1, "%")}</b>였고, <b>${n2(cb.win, 0)}%</b>의 경우 올랐습니다.
        ${avg != null ? `모든 주 평균(${sgn(avg, 1, "%")})보다 ${cb.mean > avg + 0.5 ? "<b class='up'>좋았습니다</b>" : cb.mean < avg - 0.5 ? "<b class='down'>나빴습니다</b>" : "비슷했습니다"}.` : ""}${cb.n < 8 ? " <span class='muted'>(표본이 적어 참고만 하세요)</span>" : ""}</div>`
      : `<b>지금 ${nm} ${v} = '${lab}' 구간</b><div>과거에 '${lab}' 구간이었던 주가 없어 비교할 수 없습니다. 아래 막대에서 다른 구간을 참고하세요.</div>`;
    $("#cstat").innerHTML = Object.entries(IDX_NAME).map(([k, inm]) => { const ic = all[k] && all[k].ic[S.h];
      return `<button class="cs ${k === S.idx ? "on" : ""}" data-v="${k}"><span>${inm} · ${hn}</span><b class="num ${ic == null ? "" : ic < 0 ? "down" : "up"}">${ic == null ? "—" : (ic > 0 ? "+" : "") + ic.toFixed(2)}</b><em>${icWord(ic)}</em></button>`; }).join("");
    $("#cstat").querySelectorAll(".cs").forEach((x) => x.onclick = () => { S.idx = x.dataset.v; $("#segIdx").querySelectorAll("button").forEach((y) => y.classList.toggle("on", y.dataset.v === S.idx)); drawCorr(kind, i); });
    $("#cbt").textContent = `${nm} 구간별로 샀다면: ${ix} ${hn} 평균 수익률`;
    $("#clname").textContent = ix;
    charts.cbar = new Chart($("#cbar"), { type: "bar",
      data: { labels: Z.map((z) => [z === lab ? `▶ ${z} (지금)` : z, bk[z] ? `${bk[z].n}주` : "표본 없음"]), datasets: [{ data: Z.map((z) => bk[z]?.mean ?? null), backgroundColor: CC,
        borderColor: Z.map((z) => z === lab ? "#f5cf6a" : "transparent"), borderWidth: 3, borderRadius: 4 }] },
      options: { maintainAspectRatio: false, plugins: { legend: { display: false },
        tooltip: { callbacks: { label: (c) => { const b = bk[Z[c.dataIndex]]; return b ? ` 평균 ${b.mean}% · 오른 경우 ${b.win}% · ${b.n}주` : " 표본 없음"; } } } },
        scales: { x: { ticks: { color: "#dfe7f7", font: { size: 13 } }, grid: { display: false } }, y: { ticks: { color: "#98acd0", callback: (x) => x + "%" }, grid: { color: "#3a5890" } } } } });
    const ic = cr.ic[S.h];
    $("#cnote").innerHTML = `막대 = 그 구간일 때 샀다면 ${hn} 평균 수익률 · 금색 테두리 = 지금 구간. ${ix} ${hn} 기준 맞힌 정도 <b>${ic == null ? "—" : (ic > 0 ? "+" : "") + ic.toFixed(2)}</b> → ${ic == null ? "" : ic < -0.1 ? "점수가 높을수록(" + (kind === "tc" ? "들뜰수록" : "돈이 넉넉할수록") + ") 그 뒤 수익이 낮은 편이었습니다." : ic > 0.1 ? "점수가 높을수록 그 뒤 수익도 높은 편이었습니다." : "점수와 그 뒤 수익 사이에 뚜렷한 관계가 없었습니다."} 막대를 누르면 오른 비율과 표본 수가 보입니다.`;
    const ds = D(), we = weekEnds(i, S.range === "1y" ? 53 : 160);
    charts.cline = new Chart($("#cline"), { type: "line", plugins: [bandPlugin(CC)],
      data: { labels: we.map((k) => ds[k]), datasets: [
        { label: nm, data: we.map((k) => at(kind, k)), borderColor: kind === "tc" ? "#f59e6b" : "#0fb9a5", borderWidth: 2.2, pointRadius: 0, stepped: true, yAxisID: "y", spanGaps: true },
        { label: ix, data: we.map((k) => at(S.idx, k)), borderColor: "#e8eef8", borderWidth: 1.5, pointRadius: 0, yAxisID: "y2", spanGaps: true }] },
      options: { maintainAspectRatio: false, interaction: { mode: "index", intersect: false },
        plugins: { legend: { labels: { color: "#dfe7f7", boxWidth: 12 } } },
        scales: { x: axisX(6), y: { min: 1, max: 5, ticks: { color: "#98acd0", stepSize: 1 }, grid: { color: "#3a5890" }, title: { display: true, text: "점수", color: "#98acd0" } },
          y2: { position: "right", ticks: { color: "#98acd0" }, grid: { display: false } } } } });
    const rl = cr.rolling, cut = S.range === "1y" ? 53 : 160;
    charts.croll = new Chart($("#croll"), { type: "line", plugins: [hlinePlugin([[0, "", "#8ea3cc"]])],
      data: { labels: rl.dates.slice(-cut), datasets: [{ label: "26주 상관", data: rl.v.slice(-cut), borderColor: "#e9c46a", borderWidth: 1.8, pointRadius: 0, fill: { target: { value: 0 }, above: "#34d39933", below: "#ff6b7a33" }, spanGaps: true }] },
      options: { maintainAspectRatio: false, plugins: { legend: { display: false } },
        scales: { x: axisX(6), y: { min: -1, max: 1, ticks: { color: "#98acd0", stepSize: 0.5 }, grid: { color: "#3a5890" } } } } });
  }
  function bindCorr(kind, i) {
    [["#segIdx", "idx"], ["#segH", "h"], ["#segR", "range"]].forEach(([sel, key]) => {
      $(sel).querySelectorAll("button").forEach((b) => b.onclick = () => { S[key] = b.dataset.v; $(sel).querySelectorAll("button").forEach((x) => x.classList.toggle("on", x === b)); drawCorr(kind, i); });
    });
    drawCorr(kind, i);
  }

  async function viewTC() {
    const i = idxOf(S.date), cm = (await comments(D()[i])) || {};
    $("#view").innerHTML = `<div class="grid g2">${compositeCard("tc", i, cm)}${quadrant(i, cm)}</div>
      ${pointsBlock("트렌드캐치 코멘트", asPoints(cm.tc_points, cm.tc), "tc")}
      <div class="card sec"><h3 class="tch">${M.tc.length}개 지표</h3><div class="cap">타일을 누르면 계산 방법과 의미가 나옵니다 · 점수 5 = 광기, 1 = 공포</div>
        <div class="grid tg" style="margin-top:8px">${tiles("tc", M.tc, i)}</div></div>
      <div class="sec">${heatmap("tc", M.tc, i)}</div>${corrBlock("tc")}${analysisBlock("tc")}`;
    bindInfo(); bindQuad(i, cm); bindHeat(); bindCorr("tc", i); drawMini("tc", i); bindAnalysis("tc");
  }
  function catCards(i) {
    const rows = lqCats().map((c) => {
      const ms = M.lq.filter((m) => m.cat === c), E = M.LQ_CAT_EASY[c]; let ws = 0, sc = 0;
      ms.forEach((m) => { const s = at("s_lq_" + m.key, i), w = wOf("lq", m.key, i); if (s != null) { ws += w; sc += s * w; } });
      const avg = ws ? sc / ws : null, r = avg == null ? null : Math.min(5, Math.max(1, Math.round(avg)));
      const wsum = ms.reduce((a, m) => a + wOf("lq", m.key, i), 0), col = r ? LQC[r - 1] : "#475569";
      const ans = avg == null ? "자료 없음" : avg >= 3.5 ? E.hi : avg <= 2.5 ? E.lo : E.mid;
      return `<div class="cat"><div class="ctop"><span class="cn">${c}. ${E.name}</span><span class="cw">비중 ${Math.round(wsum)}%</span></div>
        <div class="cq">${E.q}</div>
        <div class="cvl"><span class="cs num" style="color:${col}">${avg == null ? "—" : avg.toFixed(1)}</span>${r ? `<span class="pill" style="background:${col}">${M.EASY5[r]}</span>` : ""}<span class="ca">${ans}</span></div>
        <div class="cbar">${LQC.map((x) => `<i style="background:${x}"></i>`).join("")}${avg == null ? "" : `<b style="left:${(avg - 1) / 4 * 100}%"></b>`}</div>
        <div class="cm">들어간 지표: ${c === "E" ? ms.map((m) => m.short || m.name).join(" · ") : E.members + ms.filter((m) => m.isNew).map((m) => " · " + (m.short || m.name)).join("")}</div></div>`;
    }).join("");
    return `<div class="card"><h3 class="lqh">돈의 ${lqCats().length}가지 측면</h3><div class="cap">카테고리 점수 = 그 안 지표 점수의 가중평균 · 1 = 매우 빠듯 ~ 3 = 보통 ~ 5 = 매우 넉넉</div><div class="cats">${rows}</div></div>`;
  }
  async function viewLQ() {
    const i = idxOf(S.date), cm = (await comments(D()[i])) || {};
    const byCat = lqCats().map((c) => `<div class="catlb">${c}. ${M.LQ_CAT_EASY[c].name} — ${M.LQ_CATS[c]}</div><div class="grid tg">${tiles("lq", M.lq.filter((m) => m.cat === c), i)}</div>`).join("");
    $("#view").innerHTML = `<div class="grid g2">${compositeCard("lq", i, cm)}${catCards(i)}</div>
      ${pointsBlock("유동성 코멘트", asPoints(cm.lq_points, cm.lq), "lq")}
      <div class="note" style="margin:8px 2px 0">심리 × 유동성 사분면은 <button class="lnk" data-go="tc">트렌드캐치 탭</button>과 <button class="lnk" data-go="wind">풍향계 탭</button>에 있습니다.</div>
      <div class="card sec"><h3 class="lqh">${M.lq.length}개 지표</h3><div class="cap">타일을 누르면 계산 방법과 의미가 나옵니다 · 점수 5 = 풍부, 1 = 경색 · 타일의 % = 가중치</div>${byCat}</div>
      <div class="sec">${heatmap("lq", M.lq, i)}</div>${corrBlock("lq")}${analysisBlock("lq")}`;
    bindInfo(); bindGo(); bindHeat(); bindCorr("lq", i); drawMini("lq", i); bindAnalysis("lq");
  }
  function bindHeat() { $("#view").querySelectorAll(".hm .cl[data-d]").forEach((c) => c.onclick = () => setDate(c.dataset.d)); }
  function bindGo() { $("#view").querySelectorAll("[data-go]").forEach((x) => x.onclick = (e) => { e.stopPropagation(); goTab(x.dataset.go); }); }

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
      <div class="note">읽는 법: 'N주 뒤'가 크면 앞으로를 설명하는 <b>선행</b> 지표, '지난 13주 반영'이 크면 이미 지나간 흐름을 비추는 <b>후행</b> 지표입니다. 분석 기간 ${S.analysis.start} ~ ${S.analysis.end}, 공개 지연을 반영해 그 시점에 알 수 있던 값만 썼습니다. 과거 관계가 앞으로도 같다는 보장은 없습니다.</div></div>`;
  }
  function drawAnalysis(kind) {
    const el = $("#atable"); if (!el || !S.analysis) return;
    const list = (kind === "tc" ? M.tc : M.lq).map((m) => ({ key: `${kind}_${m.key}`, name: m.name, mkey: m.key })).concat([{ key: kind, name: (kind === "tc" ? "트렌드캐치" : "유동성") + " 종합", mkey: "_comp" }]);
    const rows = list.map((x) => {
      const it = S.analysis.items[x.key], r = it && it[S.aidx];
      if (!r) return `<tr><td>${x.name}</td><td colspan="7" class="muted">${esc(S.analysis.na[x.mkey] || "자료 없음")}</td></tr>`;
      return `<tr class="click" data-ak="${x.key}" data-an="${esc(x.name)}"><td>${x.name}</td><td class="muted">${r.start.slice(0, 7)}</td>${["1", "4", "13", "26"].map((h) => aCell(r.ic[h], r.sig[h])).join("")}${aCell(r.past13, false)}<td>${esc(r.role)}<div class="muted" style="font-size:12px">${esc(r.direction)}${r.stable ? "" : " · 전·후반 부호 다름"}</div></td></tr>`;
    }).join("");
    el.innerHTML = `<tr><th>지표</th><th>자료 시작</th><th class="r">1주 뒤</th><th class="r">4주 뒤</th><th class="r">13주 뒤</th><th class="r">26주 뒤</th><th class="r">지난 13주 반영</th><th>판정</th></tr>${rows}`;
    el.querySelectorAll("[data-ak]").forEach((tr) => tr.onclick = () => openAnalysis(tr.dataset.ak, tr.dataset.an));
    const ok = list.map((x) => ({ n: x.name, r: S.analysis.items[x.key]?.[S.aidx] })).filter((x) => x.r && x.r.weeks >= 300);
    const hv = (r) => r.sig["13"] ? ["13", r.ic["13"]] : ["4", r.ic["4"]];
    const lead = ok.filter((x) => x.r.sig["13"] || x.r.sig["4"]).sort((a, b) => Math.abs(hv(b.r)[1]) - Math.abs(hv(a.r)[1]));
    const lag = ok.filter((x) => Math.abs(x.r.past13 || 0) >= 0.3).map((x) => x.n);
    $("#asum").innerHTML = `요약 (${S.aidx === "spx" ? "S&P500" : "나스닥100"}, 6년 이상 자료만): 통계적으로 의미 있는 선행 지표는 ${lead.length ? lead.map((x) => { const [h, v] = hv(x.r); return `${x.n}(${h}주 뒤 ${v > 0 ? "+" : ""}${v})`; }).join(", ") : "없음"}입니다. 지난 흐름을 크게 반영하는 후행 성격은 ${lag.length ? lag.join(", ") : "없음"}입니다.`;
  }
  function bindAnalysis(kind) {
    if (!$("#segA")) return;
    $("#segA").querySelectorAll("button").forEach((b) => b.onclick = () => { S.aidx = b.dataset.v; $("#segA").querySelectorAll("button").forEach((x) => x.classList.toggle("on", x === b)); drawAnalysis(kind); });
    drawAnalysis(kind);
  }
  function analysisText(r) {
    const f = (v) => v == null ? "—" : (v > 0 ? "+" : "") + v.toFixed(2);
    return `4주 뒤 ${f(r.ic["4"])}${r.sig["4"] ? "★" : ""} · 13주 뒤 ${f(r.ic["13"])}${r.sig["13"] ? "★" : ""} · 지난 13주 반영 ${f(r.past13)} → <b>${esc(r.role)}</b>${r.direction ? ", " + esc(r.direction) : ""}${r.half ? ` (전반 ${f(r.half[0])} / 후반 ${f(r.half[1])})` : ""}`;
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
      charts.aprof = new Chart($("#aprof"), { type: "bar", data: { labels: PK, datasets: [{ data: r.profile, backgroundColor: r.profile.map((v, n) => n < 5 ? "#98acd0" : (v >= 0 ? GOOD : BAD)), borderRadius: 3 }] },
        options: { maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { y: { min: -0.8, max: 0.8, ticks: { color: "#98acd0" }, grid: { color: "#3a5890" } }, x: { ticks: { color: "#c6d4ee" }, grid: { display: false } } } } });
      $("#atext").innerHTML = `${S.aidx === "spx" ? "S&P500" : "나스닥100"} · 자료 ${r.start} 이후 ${r.weeks}주: ` + analysisText(r);
    };
    $("#segA2").querySelectorAll("button").forEach((b) => b.onclick = () => { S.aidx = b.dataset.v; $("#segA2").querySelectorAll("button").forEach((x) => x.classList.toggle("on", x === b)); draw(); });
    draw();
  }

  // ---------------------------------------------------------------- 휴대폰 알림 (OneSignal 웹 푸시)
  function initPush() {
    const btn = $("#pushbtn"); if (!btn) return;
    const ios = /iPhone|iPad|iPod/.test(navigator.userAgent) || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
    const standalone = window.navigator.standalone === true || matchMedia("(display-mode: standalone)").matches;
    const supported = "Notification" in window && "serviceWorker" in navigator && "PushManager" in window;
    const perm = () => ("Notification" in window ? Notification.permission : "default");
    const isOn = () => { const OS = window.__seoksPush; return !!(OS && OS.User && OS.User.PushSubscription && OS.User.PushSubscription.optedIn && perm() === "granted"); };
    const paint = () => { const on = isOn(); btn.classList.toggle("on", on); btn.setAttribute("aria-checked", on ? "true" : "false"); btn.title = on ? "알림 켜짐 · 누르면 끕니다" : "알림 꺼짐 · 누르면 켭니다"; };
    const guide = (t, h) => { $("#mbox").innerHTML = `<button class="x" aria-label="닫기">×</button><h2>${t}</h2>${h}`; $("#modal").classList.add("on"); $("#mbox .x").onclick = closeInfo; };
    btn.hidden = false; paint();
    const ready = () => { paint(); try { window.__seoksPush.User.PushSubscription.addEventListener("change", paint); } catch (e) {} };
    if (window.__seoksPush) ready(); else document.addEventListener("seoks-push-ready", ready);
    let busy = false;
    btn.onclick = async () => {
      if (busy) return;
      if (ios && !standalone) return guide("아이폰에서 알림 켜기", `<p>아이폰은 홈 화면에 추가한 Seoks에서만 알림을 받을 수 있습니다 (iOS 16.4 이상).</p><h4>방법</h4><p>1. Safari 아래쪽 공유 버튼을 누릅니다.<br>2. '홈 화면에 추가'를 누릅니다.<br>3. 홈 화면의 Seoks 아이콘으로 열고, 오른쪽 위 '알림' 스위치를 켭니다.</p>`);
      if (!supported) return guide("이 브라우저는 알림을 지원하지 않아요", `<p>크롬·엣지·삼성 인터넷·사파리 최신 버전에서 열어 주세요. 카카오톡 등 앱 안의 브라우저에서는 알림을 켤 수 없습니다.</p>`);
      const OS = window.__seoksPush;
      if (!OS) return guide("잠시만요", `<p>알림 기능을 불러오는 중입니다. 잠시 후 다시 눌러 주세요.</p>`);
      busy = true; btn.classList.add("busy");
      try {
        if (isOn()) { await OS.User.PushSubscription.optOut(); toast("알림을 껐어요"); }
        else if (perm() === "denied") {
          guide("알림이 차단되어 있어요", `<p>브라우저 설정에서 이 사이트의 알림이 차단된 상태라 스위치로는 켤 수 없습니다.</p><h4>푸는 방법</h4><p>· PC 크롬·엣지: 주소창 왼쪽 아이콘 → 사이트 설정 → 알림 → 허용<br>· 안드로이드 크롬: 오른쪽 위 ⋮ → 설정 → 사이트 설정 → 알림 → 이 사이트 허용<br>· 아이폰(홈 화면 앱): 설정 → 알림 → Seoks → 알림 허용</p><p>허용한 뒤 스위치를 다시 켜 주세요.</p>`);
        } else {
          if (perm() !== "granted") await OS.Notifications.requestPermission();
          if (perm() === "granted") { await OS.User.PushSubscription.optIn(); toast("알림을 켰어요 · 매일 아침 미국장 마감 후 알려드려요"); }
          else toast("알림 허용을 누르지 않아 꺼진 상태로 둡니다");
        }
      } catch (e) { console.warn("push toggle", e); toast("알림 설정 중 문제가 생겼어요. 잠시 후 다시 시도해 주세요"); }
      busy = false; btn.classList.remove("busy"); paint(); setTimeout(paint, 800);
    };
  }
  function toast(msg) {
    let t = $("#toast"); if (!t) { t = document.createElement("div"); t.id = "toast"; t.className = "toast"; document.body.appendChild(t); }
    t.textContent = msg; t.classList.add("on"); clearTimeout(toast._t); toast._t = setTimeout(() => t.classList.remove("on"), 2600);
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
      box.innerHTML = `<h4>새 소식</h4>` + (items.length ? items.map(({ d, c }) => `<div class="it ${seen && d > seen ? "new" : ""}" data-d="${d}"><div class="d">${d} (${dow(d)}) 미국 마감</div>${esc((c && ((c.wind && c.wind.headline) || (c.market && c.market.headline) || c.oneliner)) || "현황판 업데이트")}</div>`).join("") : `<div class="muted">아직 소식이 없습니다.</div>`)
        + `<div class="muted" style="font-size:11.5px;margin-top:8px">매일 아침(한국 시간 6시대) 업데이트됩니다. 휴대폰에서는 '홈 화면에 추가'하면 앱처럼 열 수 있습니다.</div>`;
      box.querySelectorAll("[data-d]").forEach((x) => x.onclick = () => { box.hidden = true; S.tab = "wind"; setDate(x.dataset.d); });
      if (last) { LS.set("seoks_seen", last); seen = last; } cnt.hidden = true;
    };
    document.addEventListener("click", (e) => { const box = $("#newsp"); if (box && !box.hidden && !e.target.closest("#newsp")) box.hidden = true; });
  }

  // ---------------------------------------------------------------- 설명 모달
  function bindInfo() { $("#view").querySelectorAll("[data-info]").forEach((el) => el.onclick = (e) => { e.stopPropagation(); openInfo(el.dataset.info); }); }
  function openInfo(spec) {
    const [kind, key] = spec.split(":"), i = idxOf(S.date), d = D()[i];
    let h = "";
    if (kind === "wind") {
      const v = windAt(i), z = zoneOf(v);
      h = `<h2>증시 풍향계</h2><div class="cur"><span class="v num" style="color:${z.color}">${v ?? "—"}</span><span class="pill" style="background:${z.color}">${z.name} · ${z.act}</span><span class="muted">${short(d)} 기준</span></div>
        <h4>무엇인가요</h4><p>${M.WIND.desc}</p><h4>계산 방법</h4><p>${windFormulaText(i)}</p>
        <h4>구간</h4><table>${S.wind.zones.slice().reverse().map((x, k, arr) => `<tr class="${x.name === z.name ? "hit" : ""}"><td><span class="sw" style="background:${x.color}"></span>${x.name}</td><td>${x.from} ~ ${k === 0 ? 100 : arr[k - 1].from}</td><td style="text-align:right">${x.act}</td></tr>`).join("")}</table>
        <h4>이렇게 정한 이유</h4><p>${M.WIND.why}</p><p style="margin-top:6px">${esc(weightsNote(i))}</p>
        <h4>한계</h4><p>계산 가능한 기간이 2023-09 이후라 상승장 위주의 표본입니다. 큰 하락장에서는 공포가 계속 깊어질 수 있어 '공포 = 기회'가 늦게 맞을 수 있습니다. 그래서 유동성을 함께 봅니다.</p>`;
    } else if (kind === "tc" || kind === "lq") {
      if (key === "_comp") h = compInfo(kind, i);
      else {
        const m = (kind === "tc" ? M.tc : M.lq).find((x) => x.key === key);
        const s = at((kind === "tc" ? "s_tc_" : "s_lq_") + key, i), L = kind === "tc" ? M.TC_LABELS : M.LQ_LABELS, col = kind === "tc" ? TCC : LQC;
        const obs = obsFor(kind, key, i);
        h = `<h2>${m.name}</h2><div class="sub">${kind === "tc" ? "트렌드캐치" : "유동성 · " + M.LQ_CAT_EASY[m.cat].name + " · 가중치 " + fmtW(wOf("lq", m.key, i)) + "%"}</div>
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
      const rows = `<tr><td class="muted">지표</td><td class="muted" style="text-align:right">가중치</td><td class="muted" style="text-align:right">점수</td></tr>` + M.tc.map((m) => { const s = at("s_tc_" + m.key, i); return `<tr><td>${m.name}</td><td style="text-align:right">${fmtW(wOf("tc", m.key, i))}%</td><td style="text-align:right">${s ?? "—"}</td></tr>`; }).join("");
      const eq = M.tc.every((m) => Math.abs(wOf("tc", m.key, i) - wOf("tc", M.tc[0].key, i)) < 0.05);
      return `<h2>트렌드캐치 종합</h2><div class="cur"><span class="v num">${v ?? "—"}</span>${pill(labelTC(v), colTC(labelTC(v)))}<span class="muted">${short(D()[i])} 기준</span></div>
        <h4>무엇인가요</h4><p>시장 심리가 얼마나 달아올랐는지(광기) 또는 얼어붙었는지(공포)를 9개 지표로 잰 점수입니다. 역발상으로 읽습니다: 공포일 때 사고, 광기일 때 파는 쪽이 과거에 유리했습니다.</p>
        <h4>계산 방법</h4><p>9개 지표 점수(1~5)의 ${eq ? "단순평균(가중치가 모두 같음)" : "가중평균"}, 소수 첫째 자리 반올림. 값이 있는 지표가 5개 이상일 때만 계산하고, 값이 없는 지표는 빼고 나머지 가중치로 다시 나눕니다. 가중치는 매주 토요일 점검합니다(풍향계 탭 아래 '가중치 점검').</p>
        <table>${rows}</table><h4>판단 구간</h4><table>${[["4.5 ~ 5.0", "광기"], ["3.5 ~ 4.5", "과열"], ["2.5 ~ 3.5", "중립"], ["1.5 ~ 2.5", "불안"], ["1.0 ~ 1.5", "공포"]].map(([r, l]) => `<tr class="${l === labelTC(v) ? "hit" : ""}"><td>${r}</td><td>${l}</td><td style="text-align:right">${M.TC_ACTION[l]}</td></tr>`).join("")}</table>`;
    }
    const rows = M.lq.map((m) => { const s = at("s_lq_" + m.key, i); return `<tr><td>${m.cat}. ${m.name}</td><td style="text-align:right">${fmtW(wOf("lq", m.key, i))}%</td><td style="text-align:right">${s ?? "—"}</td></tr>`; }).join("");
    const catP = lqCats().map((c) => `${c} ${M.LQ_CAT_EASY[c].name} ${Math.round(M.lq.filter((m) => m.cat === c).reduce((a, m) => a + wOf("lq", m.key, i), 0))}%`).join(" · ");
    return `<h2>유동성 종합</h2><div class="cur"><span class="v num">${v ?? "—"}</span>${pill(labelLQ(v), colLQ(labelLQ(v)))}<span class="muted">${short(D()[i])} 기준</span></div>
      <h4>무엇인가요</h4><p>주식시장에 돈이 얼마나 넉넉하게 돌고 있는지를 11개 지표로 잰 점수입니다. 넉넉할수록(풍부) 주식에 순풍, 빠듯할수록(경색) 역풍입니다.</p>
      <h4>계산 방법</h4><p>11개 지표 점수의 가중평균 (${catP}). 값이 없는 지표는 빼고 나머지 가중치로 다시 나눕니다 (전체 가중치의 70% 이상 있을 때만 계산). 가중치는 매주 토요일 점검합니다(풍향계 탭 아래 '가중치 점검').</p>
      <p class="sub" style="margin-top:6px">원본 시트 대비 변경: VIX 제외(그 몫은 D 안에서 비례 배분), 10년물을 5점 척도로 바꿔 D에 편입, DXY·10년물·EFFR 기준 재설정.</p>
      <table><tr><td class="muted">지표</td><td class="muted" style="text-align:right">가중치</td><td class="muted" style="text-align:right">점수</td></tr>${rows}</table>
      <h4>판단 구간</h4><table>${[["4.5 ~ 5.0", "풍부"], ["3.5 ~ 4.5", "우호"], ["2.5 ~ 3.5", "중립"], ["1.5 ~ 2.5", "긴축"], ["1.0 ~ 1.5", "경색"]].map(([r, l]) => `<tr class="${l === labelLQ(v) ? "hit" : ""}"><td>${r}</td><td>${l}</td><td style="text-align:right">${M.LQ_STANCE[l]}</td></tr>`).join("")}</table>`;
  }
  function closeInfo() { $("#modal").classList.remove("on"); }
  $("#modal").onclick = (e) => { if (e.target.id === "modal") closeInfo(); };
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") { closeInfo(); if (S.calOpen) { S.calOpen = false; renderCalPop(); } }
    if ($("#modal").classList.contains("on") || /input|textarea/i.test(e.target.tagName)) return;
    if (e.key === "ArrowLeft") step(-1); if (e.key === "ArrowRight") step(1);
  });

  // ---------------------------------------------------------------- 렌더
  async function render() {
    if (idxOf(S.date) < 0) S.date = D()[D().length - 1];
    S.date = D()[idxOf(S.date)];
    document.querySelectorAll(".tab").forEach((t) => t.classList.toggle("on", t.dataset.t === S.tab));
    $("#title").textContent = `${TAB_NM[S.tab]} | ${fmtDateKo(S.date)} 마감`;
    const isLast = S.date === S.latest.date;
    $("#stamp").textContent = isLast ? `${S.latest.generated} 업데이트` : `${S.date}(${dow(S.date)}) 기록 보기`;
    writeURL(); renderDatebar(); renderCalPop();
    Object.keys(charts).forEach(killChart);
    if (S.tab === "wind") await viewWind(); else if (S.tab === "board") await viewBoard(); else if (S.tab === "tc") await viewTC(); else await viewLQ();
  }
  document.querySelectorAll(".tab").forEach((t) => t.onclick = () => { S.tab = t.dataset.t; render(); });
  document.addEventListener("click", (e) => { if (S.calOpen && !e.target.closest(".cal") && !e.target.closest("#calbtn")) { S.calOpen = false; renderCalPop(); } });

  let wasSm = window.innerWidth < 600;
  window.addEventListener("resize", () => { const sm = window.innerWidth < 600; if (sm !== wasSm) { wasSm = sm; if (S.series && (S.tab === "wind" || S.tab === "tc")) render(); } });
  async function init() {
    try {
      S.latest = await (await fetch("data/latest.json?t=" + Date.now())).json();
      [S.series, S.corr, S.analysis, S.notes, S.wind] = await Promise.all([getJSON("data/series.json"), getJSON("data/corr.json").catch(() => null), getJSON("data/analysis.json").catch(() => null),
        getJSON("data/notes/companies.json").catch(() => ({})), getJSON("data/wind.json").catch(() => null)]);
      S.weights = await getJSON("data/weights.json").catch(() => null);
      S.factors = await getJSON("data/factors.json").catch(() => null);
      addFactors(S.factors);
      if (S.wind) S.windIdx = new Map(S.wind.dates.map((d, k) => [d, k]));
    } catch (e) {
      $("#view").innerHTML = `<div class="empty">데이터를 불러오지 못했습니다. 잠시 후 새로고침해 주세요.</div>`; return;
    }
    readURL();
    if (!S.date) S.date = S.latest.date;
    if (Chart && Chart.defaults) { Chart.defaults.font.family = getComputedStyle(document.body).fontFamily; Chart.defaults.color = "#c6d4ee"; }
    $("#calbtn").onclick = (e) => { e.stopPropagation(); S.calOpen = !S.calOpen; S.calMonth = S.date.slice(0, 7); renderCalPop(); };
    initBell(); initPush();
    render();
  }
  init();
})();
