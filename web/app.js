// Panel Analizatora CFD. Czyta dane z Supabase (tylko odczyt, po zalogowaniu). Bez konfiguracji: tryb demo.
const cfg = window.CFD_CONFIG || {};
const demo = !cfg.supabaseUrl || !cfg.supabaseAnonKey;
const $ = (sel) => document.querySelector(sel);
const state = { view: "signals", status: "open", interval: "", minImportance: "2", data: {} };
let supabase = null;

const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const num = (v, d = 5) => (v === null || v === undefined ? "–" : Number(v).toLocaleString("pl-PL", { maximumSignificantDigits: d }));
const when = (iso) => iso ? new Date(iso).toLocaleString("pl-PL", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" }) : "–";
const safeUrl = (u) => (/^https?:\/\//i.test(u || "") ? u : "");

// ---------- dane ----------
function demoData() {
  const now = Date.now(), h = 3600e3;
  return {
    signals: [
      { symbol: "GOLD", strategy: "donchian_breakout", interval: "4h", time: new Date(now - 2 * h).toISOString(), side: 1, ref_price: 4112.4, stop_loss: 4071.0, take_profit: 4195.2, rationale: "Wybicie górą z kanału 20 świec, ADX>=20", score: 2.4, context: { label: "mocny", confluence: "fundamenty zgodne (bias +0.8), newsy zgodne" }, status: "open", r_result: null },
      { symbol: "US100", strategy: "trend_pullback", interval: "1d", time: new Date(now - 30 * h).toISOString(), side: 1, ref_price: 25480, stop_loss: 25010, take_profit: 26185, rationale: "Trend wzrostowy (EMA50>EMA200), RSI wrócił nad 40", score: 1.0, context: { label: "neutralny", confluence: "fundamenty neutralne (bias +0.1), newsy neutralne" }, status: "tp", r_result: 1.46 },
      { symbol: "OIL.WTI", strategy: "mean_reversion", interval: "1h", time: new Date(now - 5 * h).toISOString(), side: -1, ref_price: 71.82, stop_loss: 72.61, take_profit: 70.4, rationale: "Konsolidacja (ADX<25), cena nad górną wstęgą, RSI>65", score: 0.4, context: { label: "pod prad", confluence: "fundamenty przeciwne (bias +1.2), newsy neutralne" }, status: "sl", r_result: -1.08 },
    ],
    news: [
      { title: "Fed holds rates, signals slower pace of cuts", url: "https://example.com/1", published: new Date(now - 0.4 * h).toISOString(), symbols: "US500,US100,GOLD,USDIDX", importance: 3, direction: { US500: -1, US100: -1, GOLD: -1, USDIDX: 1 }, reason: "Jastrzębi sygnał: mniej obniżek niż wyceniał rynek.", classifier: "llm:gemini" },
      { title: "CD Projekt podnosi prognozę sprzedaży po udanej premierze dodatku", url: "https://example.com/2", published: new Date(now - 3 * h).toISOString(), symbols: "CDR.PL", importance: 2, direction: { "CDR.PL": 1 }, reason: "Lepsze perspektywy przychodów.", classifier: "rules" },
    ],
    macro_events: [
      { time: new Date(now + 1.5 * h).toISOString(), country: "USD", name: "Core CPI m/m", importance: 3, forecast: 0.3, previous: 0.2, actual: null },
      { time: new Date(now + 20 * h).toISOString(), country: "USD", name: "Crude Oil Inventories", importance: 2, forecast: 1.2e6, previous: -0.5e6, actual: null },
    ],
    fundamental_bias: [
      { symbol: "GOLD", bias: 0.8, updated: new Date(now - 6 * h).toISOString(), components: [{ label: "realna rentowność 10Y", score: 1.1 }, { label: "szeroki indeks dolara", score: 0.5 }] },
      { symbol: "US500", bias: -0.3, updated: new Date(now - 6 * h).toISOString(), components: [{ label: "warunki finansowe (NFCI)", score: -0.2 }, { label: "spread high yield", score: -0.6 }, { label: "rentowność 10Y", score: -0.1 }] },
    ],
    source_health: [{ source: "feed:coindesk", fail_streak: 4, last_error: "HTTP 403", last_ok: new Date(now - 9 * h).toISOString() }, { source: "candles:yahoo", fail_streak: 0, last_ok: new Date(now - 0.2 * h).toISOString() }],
  };
}

async function load() {
  if (demo) return demoData();
  const since = new Date(Date.now() - 3 * 86400e3).toISOString();
  const q = (p) => p.then(({ data, error }) => { if (error) throw error; return data; });
  const [signals, news, macro_events, fundamental_bias, source_health] = await Promise.all([
    q(supabase.from("signals").select("*").order("time", { ascending: false }).limit(300)),
    q(supabase.from("news").select("title,url,published,fetched,symbols,importance,direction,reason,classifier").gte("importance", 1).gte("fetched", since).order("fetched", { ascending: false }).limit(200)),
    q(supabase.from("macro_events").select("*").gte("time", new Date(Date.now() - 6 * 3600e3).toISOString()).order("time").limit(100)),
    q(supabase.from("fundamental_bias").select("*").order("bias", { ascending: false })),
    q(supabase.from("source_health").select("*").order("fail_streak", { ascending: false })),
  ]);
  return { signals, news, macro_events, fundamental_bias, source_health };
}

// ---------- widoki ----------
const empty = (text) => `<p class="empty">${esc(text)}</p>`;
const sideWord = (s) => (s > 0 ? "LONG" : "SHORT");
const sideCls = (s) => (s > 0 ? "long" : "short");
const STATUS = { open: "otwarty", tp: "take profit", sl: "stop loss", expired: "wygasł" };

function viewSignals() {
  const rows = (state.data.signals || []).filter((s) => (!state.status || (state.status === "open" ? s.status === "open" : s.status !== "open")) && (!state.interval || s.interval === state.interval));
  if (!rows.length) return empty(state.status === "open" ? "Brak otwartych sygnałów." : "Brak sygnałów dla tych filtrów.");
  return rows.map((s) => {
    const risk = Math.abs(s.ref_price - s.stop_loss), reward = Math.abs(s.take_profit - s.ref_price);
    const result = s.r_result === null || s.r_result === undefined ? "" : `<span class="num ${s.r_result > 0 ? "pos" : "neg"}">${s.r_result > 0 ? "+" : ""}${Number(s.r_result).toFixed(2)}R</span>`;
    return `<article class="card ${sideCls(s.side)}">
      <div class="row"><span><span class="sym">${esc(s.symbol)}</span> <span class="dir ${sideCls(s.side)}">${sideWord(s.side)}</span></span><span class="meta">${esc(s.interval)} · ${when(s.time)}</span></div>
      <dl class="levels"><div><dt>Cena ref.</dt><dd>${num(s.ref_price)}</dd></div><div><dt>Stop loss</dt><dd>${num(s.stop_loss)}</dd></div><div><dt>Take profit</dt><dd>${num(s.take_profit)}</dd></div></dl>
      <div class="meta">${esc(s.strategy)} · R:R 1:${risk ? (reward / risk).toFixed(1) : "–"} · zgodność: ${esc(s.context?.label || "–")}</div>
      <p class="title">${esc(s.rationale)}</p>
      <div class="meta">${esc(s.context?.confluence || "")}</div>
      <div class="row" style="margin-top:8px"><span class="meta">Status: ${esc(STATUS[s.status] || s.status)}</span>${result}</div>
    </article>`;
  }).join("");
}

function viewNews() {
  const min = Number(state.minImportance);
  const rows = (state.data.news || []).filter((n) => (n.importance ?? 0) >= min);
  if (!rows.length) return empty("Brak newsów o tej wadze z ostatnich 3 dni.");
  const arrow = { "1": "↑", "-1": "↓", "0": "·" };
  return rows.map((n) => {
    const dirs = n.direction || {};
    const chips = String(n.symbols || "").split(",").filter(Boolean).map((s) => {
      const d = dirs[s] ?? 0;
      return `<span class="chip ${d > 0 ? "pos" : d < 0 ? "neg" : ""}">${esc(s)} ${arrow[String(d)]}</span>`;
    }).join("");
    const url = safeUrl(n.url);
    const title = url ? `<a href="${esc(url)}" target="_blank" rel="noopener noreferrer">${esc(n.title)}</a>` : esc(n.title);
    return `<article class="card ${n.importance >= 3 ? "hot" : n.importance === 2 ? "warm" : ""}">
      <div class="row"><span class="meta">${n.importance >= 3 ? "Pilne" : n.importance === 2 ? "Istotne" : "Tło"} · ${esc(n.classifier || "")}</span><span class="meta">${when(n.published || n.fetched)}</span></div>
      <p class="title">${title}</p><div class="chips">${chips}</div>
      ${n.reason ? `<p class="meta" style="margin:8px 0 0">${esc(n.reason)}</p>` : ""}
    </article>`;
  }).join("");
}

function viewMacro() {
  const rows = state.data.macro_events || [];
  if (!rows.length) return empty("Brak wydarzeń w kalendarzu.");
  return `<div class="card wide"><table><thead><tr><th>Czas</th><th>Wydarzenie</th><th class="r">Prognoza</th><th class="r">Poprz.</th><th class="r">Odczyt</th></tr></thead><tbody>${rows.map((e) => {
    const surprise = e.actual !== null && e.forecast !== null && e.actual !== e.forecast;
    return `<tr><td class="num">${when(e.time)}</td><td>${"●".repeat(e.importance || 1)} ${esc(e.country)} ${esc(e.name)}</td>
      <td class="r num">${num(e.forecast)}</td><td class="r num">${num(e.previous)}</td><td class="r num ${surprise ? "warnc" : ""}">${num(e.actual)}</td></tr>`;
  }).join("")}</tbody></table></div>`;
}

function viewBias() {
  const rows = state.data.fundamental_bias || [];
  if (!rows.length) return empty("Brak danych. Bias liczy się raz dziennie i wymaga klucza FRED.");
  return rows.map((b) => {
    const pct = Math.min(Math.abs(b.bias) / 2, 1) * 50;
    const fill = b.bias >= 0 ? `left:50%;width:${pct}%;background:var(--long)` : `right:50%;width:${pct}%;background:var(--short)`;
    const comps = (b.components || []).filter((c) => c.score !== null && c.score !== undefined).map((c) => `<tr><td>${esc(c.label)}</td><td class="r num ${c.score > 0 ? "pos" : c.score < 0 ? "neg" : ""}">${c.score > 0 ? "+" : ""}${Number(c.score).toFixed(1)}</td></tr>`).join("");
    return `<article class="card"><div class="row"><span class="sym">${esc(b.symbol)}</span><span class="num ${b.bias > 0.15 ? "pos" : b.bias < -0.15 ? "neg" : ""}">${b.bias > 0 ? "+" : ""}${Number(b.bias).toFixed(2)}</span></div>
      <div class="bar-track" role="img" aria-label="Bias ${Number(b.bias).toFixed(2)} w skali od -2 do +2"><div class="bar-fill" style="${fill}"></div></div>
      <table style="margin-top:10px"><tbody>${comps}</tbody></table><div class="meta" style="margin-top:6px">Aktualizacja: ${when(b.updated)}</div></article>`;
  }).join("");
}

function viewState() {
  const by = {};
  for (const s of state.data.signals || []) {
    const k = `${s.strategy} · ${s.interval}`;
    const g = (by[k] ??= { total: 0, resolved: 0, wins: 0, sumR: 0 });
    g.total++;
    if (s.status !== "open" && s.r_result !== null && s.r_result !== undefined) { g.resolved++; g.sumR += s.r_result; if (s.r_result > 0) g.wins++; }
  }
  const stats = Object.entries(by).sort().map(([k, g]) => `<tr><td>${esc(k)}</td><td class="r num">${g.total}</td><td class="r num">${g.resolved}</td>
    <td class="r num">${g.resolved ? Math.round(100 * g.wins / g.resolved) + "%" : "–"}</td>
    <td class="r num ${g.sumR > 0 ? "pos" : g.sumR < 0 ? "neg" : ""}">${g.resolved ? (g.sumR / g.resolved).toFixed(2) + "R" : "–"}</td></tr>`).join("");
  const health = (state.data.source_health || []).map((h) => `<tr><td>${esc(h.source)}</td>
    <td class="${h.fail_streak ? "warnc" : "pos"}">${h.fail_streak ? `błąd ×${h.fail_streak}` : "działa"}</td><td class="meta">${h.fail_streak ? esc((h.last_error || "").slice(0, 80)) : when(h.last_ok)}</td></tr>`).join("");
  return `<div class="card wide"><div class="k">Skuteczność sygnałów na żywo (ostatnie 300)</div>
    ${stats ? `<table><thead><tr><th>Strategia</th><th class="r">Sygn.</th><th class="r">Rozl.</th><th class="r">Trafne</th><th class="r">Śr. wynik</th></tr></thead><tbody>${stats}</tbody></table>` : `<p class="meta">Dziennik jest pusty.</p>`}</div>
    <div class="card wide"><div class="k">Źródła danych</div>${health ? `<table><tbody>${health}</tbody></table>` : `<p class="meta">Brak wpisów.</p>`}</div>`;
}

const VIEWS = { signals: viewSignals, news: viewNews, macro: viewMacro, bias: viewBias, state: viewState };

function select(id, label, options, value) {
  return `<label class="meta">${esc(label)} <select id="${id}">${options.map(([v, t]) => `<option value="${esc(v)}"${v === value ? " selected" : ""}>${esc(t)}</option>`).join("")}</select></label>`;
}

function render() {
  document.querySelectorAll(".tabs button").forEach((b) => b.setAttribute("aria-selected", String(b.dataset.view === state.view)));
  const f = $("#filters");
  if (state.view === "signals") {
    f.innerHTML = select("f-status", "Status", [["open", "otwarte"], ["closed", "rozliczone"], ["", "wszystkie"]], state.status) +
      select("f-interval", "Interwał", [["", "wszystkie"], ["1d", "D1"], ["4h", "H4"], ["1h", "H1"], ["30m", "M30"]], state.interval);
    $("#f-status").onchange = (e) => { state.status = e.target.value; render(); };
    $("#f-interval").onchange = (e) => { state.interval = e.target.value; render(); };
  } else if (state.view === "news") {
    f.innerHTML = select("f-imp", "Waga", [["3", "tylko pilne"], ["2", "istotne i pilne"], ["1", "wszystkie"]], state.minImportance);
    $("#f-imp").onchange = (e) => { state.minImportance = e.target.value; render(); };
  } else f.innerHTML = "";
  $("#view").innerHTML = VIEWS[state.view]();
}

async function refresh() {
  $("#stamp").textContent = "ładuję…";
  try {
    state.data = await load();
    $("#stamp").textContent = (demo ? "DEMO · " : "") + new Date().toLocaleTimeString("pl-PL", { hour: "2-digit", minute: "2-digit" });
    render();
  } catch (err) {
    $("#stamp").textContent = "błąd";
    $("#view").innerHTML = empty("Nie udało się pobrać danych: " + (err.message || err));
  }
}

function showApp() {
  $("#login").hidden = true;
  $("#app").hidden = false;
  document.querySelectorAll(".tabs button").forEach((b) => (b.onclick = () => { state.view = b.dataset.view; render(); }));
  $("#refresh").onclick = refresh;
  refresh();
  setInterval(() => { if (document.visibilityState === "visible") refresh(); }, 60000);
}

async function start() {
  if ("serviceWorker" in navigator) navigator.serviceWorker.register("sw.js").catch(() => {});
  if (demo) return showApp();
  const { createClient } = await import("https://esm.sh/@supabase/supabase-js@2");
  supabase = createClient(cfg.supabaseUrl, cfg.supabaseAnonKey);
  const { data } = await supabase.auth.getSession();
  if (data.session) return showApp();
  $("#login").hidden = false;
  supabase.auth.onAuthStateChange((_event, session) => { if (session && $("#app").hidden) showApp(); });
  $("#send-link").onclick = async () => {
    const email = $("#email").value.trim();
    if (!email) return;
    $("#login-msg").textContent = "Wysyłam…";
    const { error } = await supabase.auth.signInWithOtp({ email, options: { emailRedirectTo: location.origin + location.pathname, shouldCreateUser: false } });
    $("#login-msg").textContent = error ? "Nie udało się: " + error.message : "Link wysłany. Sprawdź pocztę.";
  };
}

start();
