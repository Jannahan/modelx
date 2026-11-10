/* Model Y · AgroShield web app.
   Reads window.MODEL_Y (ui/data/app-data.js, built by src/export_app_data.py every morning).
   The decision rule mirrors src/decision.py exactly. */
(() => {
  "use strict";
  const D = window.MODEL_Y;
  const $ = (s, el = document) => el.querySelector(s);
  const $$ = (s, el = document) => [...el.querySelectorAll(s)];
  const fmt = (n, d = 0) => n == null || isNaN(n) ? "–" : Number(n).toLocaleString("en-LK", { minimumFractionDigits: d, maximumFractionDigits: d });
  const rs = (n) => (n < 0 ? "−Rs. " + fmt(-n) : "Rs. " + fmt(n));
  const pct = (x, d = 0) => x == null ? "–" : (x * 100).toFixed(d) + "%";
  const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const dayLabel = (iso) => { const [y, m, d] = iso.split("-").map(Number); return `${d} ${MONTHS[m - 1]} ${y}`; };
  const shortDay = (iso) => { const [, m, d] = iso.split("-").map(Number); return `${d} ${MONTHS[m - 1]}`; };

  if (!D || !D.crops) { document.body.insertAdjacentHTML("afterbegin", "<p style='padding:16px'>Price data is missing. Run src/export_app_data.py.</p>"); return; }

  /* ---------- Settings (this device only) ---------- */
  const KEY = "modely.settings.v1";
  const defaults = { r_pct: D.defaults.r_pct, C: D.defaults.C, quota: D.defaults.quota, crops: D.crops.map((c) => c.id), focus: D.crops[0].id };
  function loadSettings() { try { return { ...defaults, ...JSON.parse(localStorage.getItem(KEY) || "{}") }; } catch { return { ...defaults }; } }
  function saveSettings(s) { try { localStorage.setItem(KEY, JSON.stringify(s)); return true; } catch { return false; } }
  let S = loadSettings();
  if (!D.crops.some((c) => c.id === S.focus)) S.focus = defaults.focus;
  let query = "";

  /* ---------- Decision rule (same as src/decision.py) ---------- */
  const breakEven = (w) => w * (1 + S.r_pct / 100) + S.C;
  const SIG = {
    go: { label: "OK to trade", icon: "s-go" },
    caution: { label: "Caution: buy less", icon: "s-caution" },
    stop: { label: "Do not borrow", icon: "s-stop" },
  };
  function decide(t, B, stale) {
    const { L, M, U, m_bar } = t;
    if (stale) return ["stop", stale, false];
    if (m_bar <= 0) return ["stop", "This route has lost money on average over the last 90 days.", false];
    if (U - L > D.rule.beta * m_bar) return ["stop", "Tomorrow's price is too uncertain to trust.", false];
    if (M < B) return ["stop", "The expected price is below your break-even.", false];
    if (L >= B) return ["go", "Even a bad day covers your loan and transport.", true];
    return ["caution", "Profit is likely, but a loss is possible. Use your own cash or buy less.", true];
  }
  function chanceNum(t, B) {
    const { L, M, U } = t;
    if (B <= L) return 0.03;
    if (B >= U) return 0.97;
    return B <= M ? 0.05 + 0.45 * (B - L) / (M - L) : 0.5 + 0.45 * (B - M) / (U - M);
  }
  const chanceText = (t, B) => (B <= t.L ? "under 5%" : B >= t.U ? "over 95%" : `about ${Math.round(chanceNum(t, B) * 100)}%`);

  /* ---------- Freshness ---------- */
  const nowSL = new Date(new Date().toLocaleString("en-US", { timeZone: "Asia/Colombo" }));
  const ageDays = (iso) => { const [y, m, d] = iso.split("-").map(Number); return Math.round((Date.UTC(nowSL.getFullYear(), nowSL.getMonth(), nowSL.getDate()) - Date.UTC(y, m - 1, d)) / 86400000); };
  const age = ageDays(D.bulletin_date);
  const ageText = age <= 0 ? "today" : age === 1 ? "yesterday" : `${age} days ago`;
  const staleMsg = age > D.rule.stale_after_days ? `Today's prices are not available yet. The newest HARTI bulletin is ${age} days old.` : null;

  function evaluate(c) {
    const t = c.today, B = breakEven(t.dambulla);
    const gap = t.gap_days > D.rule.stale_after_days ? `The market was closed for ${t.gap_days} days before this bulletin, so recent prices are missing.` : null;
    const [sig, reason, show] = decide(t, B, staleMsg || gap);
    return { c, t, B, sig, reason, show };
  }
  const shown = () => D.crops.filter((c) => S.crops.includes(c.id));
  const focusCrop = () => D.crops.find((c) => c.id === S.focus) || D.crops[0];

  /* ---------- Price ruler ---------- */
  function ruler(t, B, sig) {
    const W = 340, H = 86, pad = 8, y = 46, hide = sig === "stop";
    let lo, hi;
    if (hide) { lo = B * 0.6; hi = B * 1.4; } else { lo = Math.min(t.L, B); hi = Math.max(t.U, B); const p = (hi - lo) * 0.12; lo -= p; hi += p; }
    const x = (v) => pad + (v - lo) / (hi - lo) * (W - 2 * pad), bx = x(B);
    const label = hide ? `Price range hidden. Your break-even is ${rs(B)} per kilo.` : `Tomorrow's price likely between ${rs(t.L)} and ${rs(t.U)}, most likely ${rs(t.M)}. Your break-even is ${rs(B)}.`;
    let s = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${label}"><line class="axis" x1="${pad}" x2="${W - pad}" y1="${y}" y2="${y}"/>`;
    if (hide) {
      s += `<rect class="hidden-band" x="${pad}" y="${y - 13}" width="${W - 2 * pad}" height="26" rx="6"/><text class="val" x="${W * 0.22}" y="${y + 5}" text-anchor="middle">Range hidden</text>`;
    } else {
      s += `<rect class="band ${sig}" x="${x(t.L)}" y="${y - 13}" width="${Math.max(2, x(t.U) - x(t.L))}" height="26" rx="6"/>`;
      s += `<line class="med" x1="${x(t.M)}" x2="${x(t.M)}" y1="${y - 13}" y2="${y + 13}"/>`;
      s += `<text class="val" x="${x(t.L)}" y="${y + 30}" text-anchor="middle">${fmt(t.L)}</text><text class="val" x="${x(t.U)}" y="${y + 30}" text-anchor="middle">${fmt(t.U)}</text>`;
      if (Math.abs(x(t.M) - x(t.L)) > 34 && Math.abs(x(t.U) - x(t.M)) > 34) s += `<text class="tickl" x="${x(t.M)}" y="${y + 30}" text-anchor="middle">${fmt(t.M)}</text>`;
    }
    const anchor = bx < 80 ? "start" : bx > W - 80 ? "end" : "middle";
    s += `<line class="be" x1="${bx}" x2="${bx}" y1="${y - 24}" y2="${y + 17}"/><text class="be-label" x="${bx}" y="${y - 28}" text-anchor="${anchor}">Your break-even ${fmt(B)}</text>`;
    return s + "</svg>";
  }

  /* ---------- Today ---------- */
  function renderToday() {
    const all = shown().map(evaluate);
    const list = all.filter((e) => !query || e.c.name.toLowerCase().includes(query));
    const n = { go: 0, caution: 0, stop: 0 };
    all.forEach((e) => n[e.sig]++);
    const f = evaluate(focusCrop());

    $("#counts").innerHTML = `<span class="count go">OK to trade <b>${n.go}</b></span><span class="count caution">Buy less <b>${n.caution}</b></span><span class="count stop">Do not borrow <b>${n.stop}</b></span>`;
    $("#fresh-chip").textContent = `HARTI bulletin ${shortDay(D.bulletin_date)} (${ageText})`;
    const ne = D.weather && D.weather.temps && D.weather.temps.NUWARA_ELIYA;
    $("#meta-line").textContent = `Prices of ${shortDay(D.bulletin_date)} (${ageText})${ne ? ` | Nuwara Eliya ${fmt(ne.max)}°C` : ""}`;
    const banner = $("#stale-banner");
    banner.hidden = !staleMsg;
    if (staleMsg) banner.textContent = staleMsg + " All crops stay on red until new prices arrive.";

    // Stat tiles
    const [hits, tot] = f.c.hits_30;
    const cat = D.crops.reduce((a, c) => [a[0] + c.backtest.pnl["Always Trade"].catastrophic, a[1] + c.backtest.pnl["Model Y"].catastrophic], [0, 0]);
    $("#st-1").innerHTML = `<p class="label">Crops tracked</p><p class="value">${all.length}<small>crops</small></p><p class="sub">Dambulla to Colombo</p>`;
    $("#st-2").innerHTML = `<p class="label">Latest bulletin</p><p class="value">${shortDay(D.bulletin_date)}</p><p class="sub">HARTI, ${ageText}</p>`;
    $("#st-3").innerHTML = `<p class="label">Range accuracy</p><p class="value">${hits}/${tot}<small>days</small></p><p class="sub">${esc(f.c.name)}, last 30 bulletins</p>`;
    $("#st-4").innerHTML = `<p class="label">Ruinous days</p><p class="value">${cat[0]}<small>→</small> ${cat[1]}</p><p class="sub">Always trade vs Model Y, 2020–2026</p>`;

    // Weather
    const w = D.weather;
    if (w) {
      const cond = w.rain_7d_mm > w.typical_7d_mm * 1.5 ? "Wetter than usual" : w.rain_7d_mm < w.typical_7d_mm * 0.5 ? "Drier than usual" : "Normal rain";
      const dm = w.temps && w.temps.DAMBULLA;
      $("#weather").innerHTML = `<div class="w-top"><svg aria-hidden="true"><use href="#i-cloud"/></svg><div><p class="w-cond">${cond}</p><p class="w-temp">${ne ? fmt(ne.max) + "°C" : "–"}</p></div></div>
        <div class="w-rows"><span><svg aria-hidden="true"><use href="#i-rain"/></svg>${fmt(w.rain_7d_mm)} mm rain in 7 days (usual ${fmt(w.typical_7d_mm)})</span>
        ${dm ? `<span><svg aria-hidden="true"><use href="#i-temp"/></svg>Dambulla ${fmt(dm.min)}–${fmt(dm.max)}°C</span>` : ""}</div>
        <p class="w-src">Growing areas: Nuwara Eliya, Welimada, Bandarawela. Open-Meteo, to ${shortDay(w.through)}</p>`;
    }

    // Accuracy ring
    const acc = tot ? hits / tot : 0, R = 58, C = 2 * Math.PI * R;
    $("#ring").innerHTML = `<svg viewBox="0 0 148 148" role="img" aria-label="${hits} of the last ${tot} ${esc(f.c.name)} prices fell inside the forecast range">
        <circle class="track" cx="74" cy="74" r="${R}" fill="none" stroke-width="14"/>
        <circle class="arc ${acc < 0.8 ? "low" : ""}" cx="74" cy="74" r="${R}" fill="none" stroke-width="14" stroke-linecap="round" stroke-dasharray="${C}" stroke-dashoffset="${C * (1 - acc)}" transform="rotate(-90 74 74)"/>
        <text class="ring-t" x="74" y="62" text-anchor="middle">${esc(f.c.name)} range</text><text class="ring-t" x="74" y="76" text-anchor="middle">accuracy</text>
        <text class="ring-v" x="74" y="104" text-anchor="middle">${Math.round(acc * 100)}%</text></svg>
      <p class="ring-cap">Last 30 bulletins. Target 90%.</p>`;

    // Chance below break-even
    $("#chance").innerHTML = `<h3>Chance of selling below your break-even</h3><p class="g-sub">Tomorrow, with your loan and transport costs</p>
      <div class="bars">${all.map((e) => { const p = chanceNum(e.t, e.B); return `<div class="bar-row"><span>${esc(e.c.name)}</span><span class="bar-track"><span class="bar-fill" style="width:${Math.round(p * 100)}%"></span></span><span class="bar-val">${e.B <= e.t.L ? "<5%" : e.B >= e.t.U ? ">95%" : Math.round(p * 100) + "%"}</span></div>`; }).join("")}</div>`;

    // Photo chips
    const aci = Object.entries(f.c.backtest.coverage).find(([k]) => k.startsWith("CQR + ACI"));
    const news = f.c.cbsl && f.c.cbsl.reason;
    const newsShort = news ? news.text.replace(/compared to (yesterday|last \w+) /i, "").replace(/\s+/g, " ") : null;
    $("#chips").innerHTML = `<span class="chip"><span class="ic go">✓</span>Calibrated ${aci ? pct(aci[1], 1) : "–"} since 2020</span>
      ${newsShort ? `<span class="chip wide"><span class="ic ${news.direction === "up" ? "caution" : "go"}">${news.direction === "up" ? "↑" : "↓"}</span>${esc(newsShort.length > 120 ? newsShort.slice(0, 117) + "…" : newsShort)}</span>` : ""}
      <span class="chip"><span class="ic stop">!</span>${n.stop} ${n.stop === 1 ? "crop" : "crops"}: do not borrow</span>`;

    // Cards
    const cards = $("#cards");
    cards.innerHTML = list.length ? list.map((e) => {
      const { c, t, B, sig, reason, show } = e;
      const qty = sig === "go" ? `${fmt(S.quota)} kg` : sig === "caution" ? `${fmt(Math.round(S.quota / 2))} kg, own cash` : "None on credit";
      return `<li class="card ${sig}"><button type="button" data-crop="${c.id}" aria-label="${esc(c.name)}: ${SIG[sig].label}. ${esc(reason)} Open details.">
        <div class="card-top"><span class="pill"><svg aria-hidden="true"><use href="#${SIG[sig].icon}"/></svg>${SIG[sig].label}</span><span class="crop">${esc(c.name)}</span></div>
        <p class="route">Dambulla → ${esc(c.colombo_market)}</p>
        <div class="ruler">${ruler(t, B, sig)}</div>
        <dl class="kv"><dt>Break-even</dt><dd>${rs(B)}/kg</dd>
          <dt>Tomorrow, 90% range</dt><dd>${show ? `${rs(t.L)} – ${fmt(t.U)}` : "Hidden"}</dd>
          <dt>Suggested amount</dt><dd>${qty}</dd></dl>
        <p class="reason">${esc(reason)}</p><p class="more">Details and last two weeks</p></button></li>`;
    }).join("") : `<li class="panel">No crop matches “${esc(query)}”.</li>`;

    // Phone strip
    const margin = f.t.m_bar / f.t.dambulla;
    $("#strip").innerHTML = `<div><span>${esc(f.c.name)} margin</span><b class="${margin >= 0 ? "up" : "down"}">${margin >= 0 ? "+" : ""}${Math.round(margin * 100)}%</b></div>
      <div><span>Your loan</span><b>${fmt(S.r_pct, 1)}%</b></div><div><span>Transport</span><b>Rs. ${fmt(S.C, S.C % 1 ? 1 : 0)}/kg</b></div>`;

    renderAlerts(all);
  }

  /* ---------- Alerts (bell) ---------- */
  function renderAlerts(all) {
    const items = [];
    if (staleMsg) items.push(["stop", "Prices are out of date", staleMsg]);
    all.filter((e) => e.t.breakdown_advisory).forEach((e) => items.push(["caution", `${e.c.name}: Dambulla and Colombo out of step`, "Colombo prices are not following Dambulla the way they usually do this week."]));
    all.filter((e) => e.sig === "stop").forEach((e) => items.push(["stop", `${e.c.name}: do not borrow`, e.reason]));
    $("#bell-dot").hidden = !items.length;
    $("#alerts").innerHTML = items.length ? items.map(([, h, p]) => `<div class="pop-item"><strong>${esc(h)}</strong><span class="muted">${esc(p)}</span></div>`).join("") : `<div class="pop-item">No alerts today.</div>`;
  }
  $("#bell").addEventListener("click", (e) => {
    e.stopPropagation();
    const pop = $("#alerts"), open = pop.hidden;
    pop.hidden = !open; $("#bell").setAttribute("aria-expanded", String(open));
  });
  document.addEventListener("click", (e) => { if (!e.target.closest(".bell-wrap")) { $("#alerts").hidden = true; $("#bell").setAttribute("aria-expanded", "false"); } });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") { $("#alerts").hidden = true; $("#bell").setAttribute("aria-expanded", "false"); } });

  /* ---------- Detail sheet ---------- */
  function priceChart(rows) {
    const pts = rows.filter((r) => r.colombo != null);
    if (pts.length < 2) return "";
    const W = 340, H = 170, pl = 40, pr = 8, pt = 10, pb = 24;
    const vals = pts.flatMap((r) => [r.colombo, r.dambulla, r.lo, r.hi]).filter((v) => v != null);
    let lo = Math.min(...vals), hi = Math.max(...vals); const pad = (hi - lo) * 0.08 || 10; lo -= pad; hi += pad;
    const x = (i) => pl + i * (W - pl - pr) / (pts.length - 1), y = (v) => pt + (hi - v) / (hi - lo) * (H - pt - pb);
    let s = `<svg class="chart" viewBox="0 0 ${W} ${H}" role="img" aria-label="Colombo and Dambulla prices over the last ${pts.length} bulletins, with the range forecast for each day">`;
    [lo + pad, (lo + hi) / 2, hi - pad].forEach((v) => { s += `<line class="grid" x1="${pl}" x2="${W - pr}" y1="${y(v)}" y2="${y(v)}"/><text x="${pl - 4}" y="${y(v) + 4}" text-anchor="end">${fmt(v)}</text>`; });
    pts.forEach((r, i) => { if (r.lo != null) s += `<rect class="rng" x="${x(i) - 5}" y="${y(r.hi)}" width="10" height="${Math.max(1, y(r.lo) - y(r.hi))}" rx="2"/>`; });
    s += `<path class="dam" d="${pts.map((r, i) => `${i ? "L" : "M"}${x(i)},${y(r.dambulla)}`).join("")}"/><path class="col" d="${pts.map((r, i) => `${i ? "L" : "M"}${x(i)},${y(r.colombo)}`).join("")}"/>`;
    pts.forEach((r, i) => { if (r.lo == null) return; const miss = r.colombo < r.lo || r.colombo > r.hi; s += `<circle class="${miss ? "miss" : "hit"}" cx="${x(i)}" cy="${y(r.colombo)}" r="${miss ? 4.5 : 3}"><title>${shortDay(r.date)}: Rs. ${fmt(r.colombo)}${miss ? ", outside its range" : ""}</title></circle>`; });
    s += `<text x="${pl}" y="${H - 6}">${shortDay(pts[0].date)}</text><text x="${W - pr}" y="${H - 6}" text-anchor="end">${shortDay(pts[pts.length - 1].date)}</text>`;
    return s + "</svg>";
  }
  const chartLegend = `<div class="legend"><span style="color:var(--ink)"><i></i>Colombo price</span><span><i style="background:var(--muted)"></i>Dambulla price</span><span style="color:var(--caution)"><i style="height:10px;width:10px;opacity:.6"></i>Range forecast</span><span style="color:var(--stop)"><i style="height:8px;width:8px;border-radius:50%"></i>Outside range</span></div>`;

  function openSheet(id) {
    const e = evaluate(D.crops.find((k) => k.id === id));
    const { c, t, B, sig, reason, show } = e;
    const [hits, n] = c.hits_30;
    let h = `<div class="sheet-head"><div><h2 id="sheet-title">${esc(c.name)}</h2><p class="muted">Dambulla → ${esc(c.colombo_market)}, bulletin of ${dayLabel(t.date)}</p></div><button class="close" type="button" aria-label="Close">×</button></div>
      <div class="card ${sig}"><div class="card-inner"><span class="pill"><svg aria-hidden="true"><use href="#${SIG[sig].icon}"/></svg>${SIG[sig].label}</span><p class="reason">${esc(reason)}</p><div class="ruler">${ruler(t, B, sig)}</div>
      <div class="ruler-key">${show ? "<span>Band: 9 in 10 chance the price lands here</span><span>Solid line: most likely</span>" : ""}<span>Dashed line: your break-even</span></div></div></div>`;
    if (show) h += `<div class="block"><h3>Chance of selling below your break-even</h3><p class="chance">${chanceText(t, B)}</p><p class="muted">${fmt(S.quota)} kg costs you ${rs(S.quota * B)} with interest and transport. On a bad day (bottom of the band) you would get back ${rs(S.quota * t.L)}.</p></div>`;
    else h += `<div class="block"><h3>Why the range is hidden</h3><p class="muted">On a red day we don't show a price, so a hopeful number can't tempt you into a loan the data doesn't support.</p></div>`;
    h += `<div class="block"><h3>The last two weeks</h3>${priceChart(c.recent)}${chartLegend}</div>`;
    h += `<div class="block"><h3>How often the range was right lately</h3><p><strong>${hits} of the last ${n}</strong> Colombo prices fell inside their range.</p></div>`;
    if (t.breakdown_advisory) h += `<div class="block note warn"><h3>Dambulla and Colombo prices are out of step</h3><p>Colombo is not following Dambulla the way it usually does this week. Be careful relying on yesterday's spread.</p></div>`;
    if (c.cbsl && c.cbsl.reason) h += `<div class="block"><h3>What the Central Bank reported</h3><p class="note">${esc(c.cbsl.reason.text)}</p><p class="muted" style="margin-top:4px">CBSL Daily Price Report, ${dayLabel(c.cbsl.reason.date)}</p></div>`;
    h += `<p class="footnote">Ranges are right about 9 times in 10, not always. Decision support, not financial advice.</p>`;
    $("#sheet-body").innerHTML = h;
    $(".close", $("#sheet")).addEventListener("click", () => $("#sheet").close());
    $("#sheet").showModal();
  }
  $("#sheet").addEventListener("click", (e) => { if (e.target.id === "sheet") e.target.close(); });
  $("#cards").addEventListener("click", (e) => { const b = e.target.closest("button[data-crop]"); if (b) openSheet(b.dataset.crop); });

  /* ---------- Calculator ---------- */
  function fillForm() {
    $("#in-r").value = S.r_pct; $("#in-c").value = S.C; $("#in-q").value = S.quota;
    $("#crop-toggles").innerHTML = D.crops.map((c) => `<label><input type="checkbox" value="${c.id}" ${S.crops.includes(c.id) ? "checked" : ""}>${esc(c.name)}</label>`).join("");
    $("#qc-crop").innerHTML = D.crops.map((c) => `<option value="${c.id}" ${c.id === S.focus ? "selected" : ""}>${esc(c.name)}</option>`).join("");
    seedQuick();
  }
  function seedQuick() {
    const e = evaluate(D.crops.find((c) => c.id === $("#qc-crop").value) || focusCrop());
    $("#qc-buy").value = e.t.dambulla; $("#qc-sell").value = e.show ? e.t.M : e.t.dambulla;
    renderQuick();
  }
  function renderQuick() {
    const e = evaluate(D.crops.find((c) => c.id === $("#qc-crop").value) || focusCrop());
    const buy = parseFloat($("#qc-buy").value), sell = parseFloat($("#qc-sell").value);
    const out = $("#qc-out");
    if (!(buy > 0) || !(sell > 0)) { out.className = "qc-out"; out.textContent = "Enter a buying and a selling price."; return; }
    const B = breakEven(buy), perKg = sell - B, total = perKg * S.quota;
    out.className = "qc-out " + (perKg >= 0 ? "go" : "stop");
    out.innerHTML = `<span>${perKg >= 0 ? "Profit" : "Loss"} on ${fmt(S.quota)} kg</span><strong>${rs(total)}</strong>
      <span>Break-even ${rs(B)}/kg, so ${perKg >= 0 ? "you keep" : "you lose"} ${rs(Math.abs(perKg))} per kg.</span>
      <p class="muted" style="margin-top:6px">${e.show ? `Model Y's 90% range for tomorrow: ${rs(e.t.L)} – ${fmt(e.t.U)}.` : `Model Y says do not borrow for ${esc(e.c.name.toLowerCase())} today.`}</p>`;
  }
  ["#qc-buy", "#qc-sell"].forEach((s) => $(s).addEventListener("input", renderQuick));
  $("#qc-crop").addEventListener("change", seedQuick);
  $("#settings").addEventListener("submit", (e) => {
    e.preventDefault();
    const num = (id, lo, hi, fb) => { const v = parseFloat($(id).value); return isNaN(v) ? fb : Math.min(hi, Math.max(lo, v)); };
    S = { ...S, r_pct: num("#in-r", 0, 50, defaults.r_pct), C: num("#in-c", 0, 500, defaults.C), quota: Math.round(num("#in-q", 1, 100000, defaults.quota)),
          crops: $$("#crop-toggles input:checked").map((i) => i.value) };
    const ok = saveSettings(S);
    fillForm(); renderToday();
    $("#saved").textContent = ok ? "Saved on this device. Today's signals now use your costs." : "Applied for now. This browser blocks saving, so they reset next time.";
  });
  $("#reset").addEventListener("click", () => { S = { ...defaults, focus: S.focus }; saveSettings(S); fillForm(); renderToday(); $("#saved").textContent = "Back to typical costs."; });

  /* ---------- Live market ---------- */
  function renderMarket() {
    $("#mk-lede").textContent = `Latest prices from the HARTI bulletin of ${dayLabel(D.bulletin_date)} and the Central Bank's daily price report, with each day's forecast range.`;
    $("#market").innerHTML = D.crops.map((c) => {
      const last = c.recent[c.recent.length - 1] || {}, prev = c.recent[c.recent.length - 2] || {};
      const ch = (a, b) => (a != null && b ? `${a >= b ? "▲" : "▼"} ${fmt(Math.abs(a - b))}` : "");
      const cb = c.cbsl && c.cbsl.prices;
      const cbRows = cb ? cb.rows.filter((r) => r.type === "retail").map((r) => `${esc(r.market)} ${rs(r.price)}`).join(", ") : null;
      return `<article class="panel"><div class="mk-head"><h3 class="panel-h">${esc(c.name)}</h3><span class="muted">${shortDay(last.date || D.bulletin_date)}</span></div>
        <div class="mk-prices"><div><span>Dambulla wholesale</span><b>${rs(last.dambulla)}</b> <small class="muted">${ch(last.dambulla, prev.dambulla)}</small></div>
        <div><span>${esc(c.colombo_market)} wholesale</span><b>${rs(last.colombo)}</b> <small class="muted">${ch(last.colombo, prev.colombo)}</small></div></div>
        ${priceChart(c.recent)}
        ${cbRows ? `<p class="muted" style="margin-top:8px">CBSL retail, ${shortDay(cb.date)}: ${cbRows}</p>` : ""}
        ${c.cbsl && c.cbsl.reason ? `<p class="note" style="margin-top:8px">${esc(c.cbsl.reason.text)}</p>` : `<p class="muted" style="margin-top:8px">The Central Bank report does not cover ${esc(c.name.toLowerCase())}.</p>`}
      </article>`;
    }).join("") + `<div class="panel" style="grid-column:1/-1">${chartLegend}</div>`;
  }

  /* ---------- Analysis ---------- */
  let anCrop = S.focus;
  function lineChart(series, o) {
    const all = series.flatMap((s) => s.data); if (all.length < 2) return "<p class='muted'>Not enough data.</p>";
    const W = 560, H = 220, pl = 42, pr = 10, pt = 10, pb = 26, dates = [...new Set(all.map((d) => d[0]))].sort();
    const x = (d) => pl + dates.indexOf(d) * (W - pl - pr) / Math.max(1, dates.length - 1), y = (v) => pt + (o.hi - v) / (o.hi - o.lo) * (H - pt - pb);
    let s = `<svg class="chart" viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(o.label)}">`;
    o.ticks.forEach((v) => { s += `<line class="grid" x1="${pl}" x2="${W - pr}" y1="${y(v)}" y2="${y(v)}"/><text x="${pl - 6}" y="${y(v) + 4}" text-anchor="end">${o.tf(v)}</text>`; });
    if (o.target != null) s += `<line class="target" x1="${pl}" x2="${W - pr}" y1="${y(o.target)}" y2="${y(o.target)}"/>`;
    series.forEach((se) => { s += `<path class="${se.cls}" d="${se.data.map((d, i) => `${i ? "L" : "M"}${x(d[0])},${y(Math.max(o.lo, Math.min(o.hi, d[1])))}`).join("")}"/>`; });
    dates.filter((d) => d.endsWith("-01")).forEach((d) => { s += `<text x="${x(d)}" y="${H - 6}" text-anchor="middle">${d.slice(0, 4)}</text>`; });
    return s + "</svg>";
  }
  function barChart(data, label) {
    if (!data.length) return "";
    const W = 560, H = 150, pl = 42, pr = 10, pt = 8, pb = 26, bw = (W - pl - pr) / data.length, y = (v) => pt + (1 - v) * (H - pt - pb);
    let s = `<svg class="chart" viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(label)}">`;
    [0, 0.5, 1].forEach((v) => { s += `<line class="grid" x1="${pl}" x2="${W - pr}" y1="${y(v)}" y2="${y(v)}"/><text x="${pl - 6}" y="${y(v) + 4}" text-anchor="end">${v * 100}%</text>`; });
    data.forEach((d, i) => { s += `<rect class="bar" x="${pl + i * bw}" y="${y(d[1])}" width="${Math.max(1, bw - 1)}" height="${y(0) - y(d[1])}"><title>${d[0]}: ${pct(d[1])} of days flagged</title></rect>`; if (d[0].endsWith("-01")) s += `<text x="${pl + i * bw}" y="${H - 6}">${d[0].slice(0, 4)}</text>`; });
    return s + "</svg>";
  }
  function interestChart(rows, rStar) {
    if (!rows.length) return "";
    const W = 560, H = 200, pl = 42, pr = 10, pt = 10, pb = 30, maxR = rows[rows.length - 1].r, x = (r) => pl + r / maxR * (W - pl - pr), y = (v) => pt + (1 - v) * (H - pt - pb);
    let s = `<svg class="chart" viewBox="0 0 ${W} ${H}" role="img" aria-label="Share of losing days by loan interest rate">`;
    [0, 0.25, 0.5, 0.75, 1].forEach((v) => { s += `<line class="grid" x1="${pl}" x2="${W - pr}" y1="${y(v)}" y2="${y(v)}"/><text x="${pl - 6}" y="${y(v) + 4}" text-anchor="end">${v * 100}%</text>`; });
    s += `<path class="lossline" d="${rows.map((r, i) => `${i ? "L" : "M"}${x(r.r)},${y(r.always_loss_rate)}`).join("")}"/>`;
    rows.forEach((r) => { s += `<circle class="dot" cx="${x(r.r)}" cy="${y(r.always_loss_rate)}" r="3.5"><title>${(r.r * 100).toFixed(1)}% per trip: ${pct(r.always_loss_rate)} of days lose money</title></circle><text x="${x(r.r)}" y="${H - 8}" text-anchor="middle">${(r.r * 100).toFixed(r.r < 0.01 && r.r > 0 ? 1 : 0)}%</text>`; });
    if (rStar > 0 && rStar <= maxR) s += `<line class="target" x1="${x(rStar)}" x2="${x(rStar)}" y1="${pt}" y2="${H - pb}"/>`;
    return s + "</svg>";
  }
  function renderAnalysis() {
    $("#an-crops").innerHTML = D.crops.map((c) => `<button role="tab" aria-selected="${c.id === anCrop}" data-crop="${c.id}">${esc(c.name)}</button>`).join("");
    const c = D.crops.find((k) => k.id === anCrop), b = c.backtest, cov = b.coverage;
    const aciKey = Object.keys(cov).find((k) => k.startsWith("CQR + ACI")), pnl = b.pnl, rStar = b.break_even_interest_rate;
    const rc = b.refusal_cost || {}, bw = b.breakdown_warning || { shocks: {} }, mae = b.mae || {}, ab = D.ablation_weather && D.ablation_weather[c.id];
    const rowsP = [["Always trade", pnl["Always Trade"]], ["Trade if yesterday's spread paid", pnl["Yesterday's Spread"]], ["Follow Model Y", pnl["Model Y"]]];
    let h = `<div class="an-grid">`;
    h += `<div class="panel span2"><h2>Is the 90% range honest?</h2><p class="q">Share of real Colombo prices inside the range, over the previous 90 market days.</p>
      <p class="answer">Model Y: <strong>${pct(cov[aciKey], 1)}</strong> of ${fmt(b.days)} days. The same model without calibration: ${pct(cov["Raw LightGBM"], 1)}.</p>
      ${lineChart([{ cls: "raw", data: c.calibration_monthly.raw }, { cls: "aci", data: c.calibration_monthly.aci }], { lo: 0.5, hi: 1, ticks: [0.5, 0.6, 0.7, 0.8, 0.9, 1], tf: (v) => Math.round(v * 100) + "%", target: 0.9, label: "Rolling 90-day coverage over time" })}
      <div class="legend"><span style="color:var(--brand)"><i></i>Model Y (CQR + ACI)</span><span><i style="background:var(--muted)"></i>Uncalibrated LightGBM</span><span style="color:var(--caution)"><i></i>90% target</span></div>
      <div class="tbl-wrap" style="margin-top:10px"><table><thead><tr><th>Method</th><th>Coverage</th><th>Range width</th></tr></thead><tbody>
      ${Object.keys(cov).map((k) => `<tr class="${k === aciKey ? "ours" : ""}"><td>${esc(k)}</td><td>${pct(cov[k], 1)}</td><td>${fmt(b.width_pct[k], 0)}% of price</td></tr>`).join("")}</tbody></table></div></div>`;
    h += `<div class="panel span2"><h2>Would following it have protected a borrower?</h2><p class="q">${fmt(b.days)} market days, 100 kg a day, loan 0.3% per trip, transport Rs. 6/kg. Amber days buy half.</p>
      <div class="tbl-wrap"><table><thead><tr><th>Strategy</th><th>Profit</th><th>Days traded</th><th>Ruinous days</th><th>Worst day</th></tr></thead><tbody>
      ${rowsP.map(([n, v]) => `<tr class="${n.startsWith("Follow") ? "ours" : ""}"><td>${n}</td><td class="${v.total_pnl < 0 ? "neg" : ""}">${rs(v.total_pnl)}</td><td>${fmt(v.days_traded)}</td><td>${fmt(v.catastrophic)}</td><td class="neg">${rs(v.worst_day)}</td></tr>`).join("")}
      </tbody></table></div><p class="muted" style="margin-top:6px">A ruinous day loses more than 30% of what was spent.</p></div>`;
    h += `<div class="panel"><h2>Are the red days justified?</h2><p class="q">Red days on which trading would really have lost money.</p>
      <p class="answer"><strong>${pct(b.red_days_lose)}</strong> of ${fmt(rc.red_days)} red days, against ${pct(b.base_loss_rate)} on an average day.</p>
      <p class="muted">The price of safety: ${pct(rc.red_days_profitable_share)} of red days would have made money (${rs(rc.profit_forgone_rs)} in total). Losses avoided: ${rs(rc.losses_avoided_rs)}.</p></div>`;
    h += `<div class="panel"><h2>At what interest rate does trading stop paying?</h2><p class="q">Share of losing days for a trader who always trades ${esc(c.name.toLowerCase())}, by loan cost per trip.</p>
      ${interestChart(b.by_interest_rate || [], rStar)}<p class="answer">${rStar > 0 ? `Trading stops paying on average above <strong>${(rStar * 100).toFixed(1)}%</strong> per trip.` : `<strong>Even at 0% interest</strong> this route lost money on average.`}</p></div>`;
    h += `<div class="panel span2"><h2>When did the Dambulla–Colombo link break?</h2><p class="q">Share of days each month the breakdown detector flagged prices moving out of step.</p>
      ${barChart(c.breakdown_monthly, "Monthly share of days with a breakdown flag")}
      <p class="muted">${Object.entries(bw.shocks || {}).map(([k, v]) => `${esc(k)}: ${v.flag_rate_30d_before == null ? "no bulletins before it" : pct(v.flag_rate_30d_before) + " of the 30 days before were flagged"}`).join(". ")}. Usual rate: ${pct(bw.base_flag_rate)}. On 2016–2019 data, forcing red on this flag cost more than it saved, so it is a warning, not a refusal.</p></div>`;
    h += `<div class="panel"><h2>How close is the most likely price?</h2><p class="q">Average error of the median forecast, Rs. per kg.</p><div class="tbl-wrap"><table><tbody>
      ${Object.entries(mae).map(([k, v]) => `<tr class="${k.startsWith("LightGBM") ? "ours" : ""}"><td>${esc(k)}</td><td>${rs(v)}</td></tr>`).join("")}</tbody></table></div></div>`;
    if (ab) { const w = ab["with weather"], n = ab["without weather"];
      h += `<div class="panel"><h2>Does rainfall help?</h2><p class="q">Same model with and without Open-Meteo rain in the growing areas.</p><div class="tbl-wrap"><table><thead><tr><th></th><th>With rain</th><th>Without</th></tr></thead><tbody>
        <tr><td>Coverage</td><td>${pct(w.coverage, 1)}</td><td>${pct(n.coverage, 1)}</td></tr><tr><td>Range width</td><td>${fmt(w.width_pct, 1)}%</td><td>${fmt(n.width_pct, 1)}%</td></tr>
        <tr><td>Median error</td><td>${rs(w.mae_median)}</td><td>${rs(n.mae_median)}</td></tr></tbody></table></div></div>`; }
    $("#analysis").innerHTML = h + "</div>";
  }
  $("#an-crops").addEventListener("click", (e) => { const b = e.target.closest("button[data-crop]"); if (b) { anCrop = b.dataset.crop; renderAnalysis(); } });

  /* ---------- About the data ---------- */
  function renderAbout() {
    const dq = D.data_quality || {};
    const rs_ = Object.values(dq.cross_check || {}).flatMap((v) => Object.values(v).map((x) => x.pearson_r));
    $("#about").innerHTML = `<div class="an-grid"><div class="panel span2"><h2>Sources</h2><div class="tbl-wrap"><table><tbody>
      <tr><td>HARTI daily food bulletins (main prices)</td><td>${dq.bulletins ? fmt(dq.bulletins.parsed) + " parsed" : "–"}, Jun 2015 – today</td></tr>
      <tr><td>Bulletins missing on HARTI's own server</td><td>${fmt(dq.missing_404)}</td></tr>
      <tr><td>CBSL daily price reports (second source, supply reasons)</td><td>${dq.cbsl ? fmt(dq.cbsl.parsed) + " parsed, Aug 2016 – today" : "–"}</td></tr>
      ${rs_.length ? `<tr><td>HARTI and CBSL agree on the same day (correlation)</td><td>${Math.min(...rs_).toFixed(2)} to ${Math.max(...rs_).toFixed(2)}</td></tr>` : ""}
      <tr><td>Open-Meteo rainfall and temperature</td><td>4 stations, daily since 2015</td></tr>
      <tr><td>Large price jumps kept and flagged for review</td><td>${fmt(dq.jumps_flagged)}</td></tr></tbody></table></div></div>
      <div class="panel"><h2>How a signal is made</h2><p class="q">Every morning at 06:00 and 10:00 Sri Lanka time</p><ol style="margin:0;padding-left:20px;display:grid;gap:6px">
        <li>New HARTI and CBSL bulletins and rainfall are downloaded.</li><li>LightGBM forecasts tomorrow's Colombo price at the 5th, 50th and 95th percentile.</li>
        <li>CQR + ACI calibration widens the range until about 9 in 10 real prices land inside it.</li><li>Your break-even is compared with the range: green, amber or red.</li></ol></div>
      <div class="panel"><h2>Gaps we don't hide</h2><p class="muted">The COVID-19 lockdown left no bulletins for 94 days in 2020, and most of February 2017 is missing on HARTI's server. We never fill these in. When prices are more than 4 days old, every crop turns red.</p>
        <p class="muted" style="margin-top:8px">Updated ${esc(D.generated_at.replace("T", " "))}. Code and full results: github.com/Jannahan/modelx</p></div></div>`;
  }

  /* ---------- Navigation ---------- */
  const TITLES = { today: "Today's market", calc: "Calculator", market: "Live market", analysis: "Analysis", about: "About the data" };
  function show(view) {
    if (!TITLES[view]) view = "today";
    if ($("#sheet").open) $("#sheet").close();
    $$(".view").forEach((v) => (v.hidden = v.id !== "view-" + view));
    $$("[data-view]").forEach((b) => { if (b.dataset.view === view) b.setAttribute("aria-current", "page"); else b.removeAttribute("aria-current"); });
    $("#page-title").textContent = TITLES[view];
    $(".focus-select").style.visibility = view === "today" ? "visible" : "hidden";
    if (view === "analysis") renderAnalysis();
    if (view === "market") renderMarket();
    if (view === "about") renderAbout();
    window.scrollTo(0, 0);
  }
  const go = (v) => { history.replaceState(null, "", "#" + v); show(v); };
  $$("[data-view]").forEach((b) => b.addEventListener("click", () => go(b.dataset.view)));
  $$("[data-goto]").forEach((b) => b.addEventListener("click", () => go(b.dataset.goto)));
  window.addEventListener("hashchange", () => show(location.hash.slice(1)));

  $("#focus").innerHTML = D.crops.map((c) => `<option value="${c.id}" ${c.id === S.focus ? "selected" : ""}>${esc(c.name)}: Dambulla → ${esc(c.colombo_market)}</option>`).join("");
  $("#focus").addEventListener("change", (e) => { S.focus = e.target.value; anCrop = S.focus; saveSettings(S); renderToday(); });
  $("#search").addEventListener("input", (e) => { query = e.target.value.trim().toLowerCase(); renderToday(); });

  fillForm();
  renderToday();
  show(location.hash.slice(1) || "today");

  if ("serviceWorker" in navigator && location.protocol.startsWith("http")) navigator.serviceWorker.register("sw.js").catch(() => {});
})();
