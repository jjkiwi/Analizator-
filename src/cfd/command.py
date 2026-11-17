"""Dashboard "centrum dowodzenia": jeden samodzielny plik HTML na telefon i komputer.

Czesc statyczna (generowana co godzine): mapa rynku, wykresy z formacjami, prognozy modelu z ich jakoscia, trend miesieczny,
spolki, sygnaly, kalendarz makro. Czesc na zywo (doczytywana w przegladarce co 2 minuty z live.json): pasek notowan,
pasek i lista newsow z ruchem ceny od publikacji. Bez zewnetrznych bibliotek.
"""
from __future__ import annotations

import html
import json
from datetime import datetime

CATS = {"indices": "Indeksy", "commodities": "Surowce", "metals": "Metale", "crypto": "Krypto", "stocks": "Akcje"}

CSS = """
:root{--bg:#f3f5f8;--panel:#fff;--fg:#151a21;--mut:#5d6672;--line:#dde2e8;--up:#12804a;--down:#c42b35;--warn:#9a6200;
--accent:#2f6fde;--chip:#eef1f5;--good:#e2f3e8;--none:#f8e8ea;--tape:#0f141a;--tapefg:#e8edf3}
@media(prefers-color-scheme:dark){:root{--bg:#0b0f14;--panel:#121820;--fg:#e6ebf1;--mut:#8b95a2;--line:#232c37;--up:#3ccf7b;
--down:#ff5c66;--warn:#e0a73e;--accent:#5b9bff;--chip:#1b232d;--good:#14301f;--none:#351a1e;--tape:#070a0e;--tapefg:#e6ebf1}}
*{box-sizing:border-box}html,body{margin:0}body{background:var(--bg);color:var(--fg);font:14px/1.45 system-ui,-apple-system,"Segoe UI",sans-serif}
a{color:inherit}.mut{color:var(--mut)}.small{font-size:12.5px}.up{color:var(--up)}.down{color:var(--down)}.warn{color:var(--warn)}
header{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:10px 16px;background:var(--panel);border-bottom:1px solid var(--line);position:sticky;top:0;z-index:5}
header h1{font-size:17px;margin:0;letter-spacing:.02em}.dot{display:inline-block;width:8px;height:8px;border-radius:50%;background:var(--mut);margin-right:6px}
.dot.on{background:var(--up);box-shadow:0 0 0 3px color-mix(in srgb,var(--up) 25%,transparent)}
.tape{background:var(--tape);color:var(--tapefg);overflow:hidden;white-space:nowrap;border-bottom:1px solid var(--line)}
.tape .row{display:inline-flex;gap:22px;padding:7px 16px;animation:scroll 60s linear infinite}
.tape:hover .row{animation-play-state:paused}.q b{font-weight:600;margin-right:6px}.q span{font-variant-numeric:tabular-nums}
.ticker{background:var(--panel);overflow:hidden;white-space:nowrap;border-bottom:1px solid var(--line);font-size:13px}
.ticker .row{display:inline-flex;gap:36px;padding:6px 16px;animation:scroll 120s linear infinite}.ticker:hover .row{animation-play-state:paused}
@keyframes scroll{from{transform:translateX(0)}to{transform:translateX(-50%)}}
@media(prefers-reduced-motion:reduce){.tape .row,.ticker .row{animation:none}}
main{padding:14px 16px 32px;max-width:1500px;margin:0 auto}
.layout{display:grid;gap:14px;grid-template-columns:repeat(12,1fr)}
.panel{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:12px;min-width:0}
.panel h2{font-size:14px;margin:0 0 10px;display:flex;justify-content:space-between;align-items:baseline;gap:8px;text-transform:uppercase;letter-spacing:.05em}
.panel h2 small{font-weight:400;text-transform:none;letter-spacing:0;color:var(--mut)}
.w12{grid-column:span 12}.w8{grid-column:span 8}.w7{grid-column:span 7}.w6{grid-column:span 6}.w5{grid-column:span 5}.w4{grid-column:span 4}
@media(max-width:1100px){.w8,.w7,.w6,.w5,.w4{grid-column:span 12}}
.news{list-style:none;margin:0;padding:0;max-height:560px;overflow:auto}
.news li{padding:8px 2px;border-bottom:1px solid var(--line);display:grid;grid-template-columns:52px 1fr auto;gap:8px;align-items:start}
.news time{color:var(--mut);font-variant-numeric:tabular-nums;font-size:12px}.news a{text-decoration:none}.news a:hover{text-decoration:underline}
.imp{display:inline-block;width:8px;height:8px;border-radius:2px;margin-right:6px;vertical-align:1px}.i3{background:var(--down)}.i2{background:var(--warn)}.i1{background:var(--mut)}
.mv{font-variant-numeric:tabular-nums;font-size:12px;white-space:nowrap;text-align:right}
.chips{display:flex;flex-wrap:wrap;gap:4px;margin-top:4px}.chip{background:var(--chip);border-radius:999px;padding:1px 8px;font-size:11.5px;color:var(--mut)}
.chip.ok{color:var(--up)}.chip.bad{color:var(--down)}
.heat{display:grid;grid-template-columns:repeat(auto-fill,minmax(86px,1fr));gap:4px}
.tile{border-radius:6px;padding:6px 7px;font-size:12px;line-height:1.25;color:#fff;min-height:46px}
.tile b{display:block;font-size:12.5px}.tile span{font-variant-numeric:tabular-nums;opacity:.95}
.cat{margin:10px 0 4px;font-size:11.5px;color:var(--mut);text-transform:uppercase;letter-spacing:.06em}
.tabs{display:flex;flex-wrap:wrap;gap:4px;margin-bottom:8px}.tabs button{border:1px solid var(--line);background:var(--chip);color:var(--fg);border-radius:6px;padding:3px 9px;font:inherit;font-size:12.5px;cursor:pointer}
.tabs button[aria-pressed=true]{background:var(--accent);border-color:var(--accent);color:#fff}
.chart svg{width:100%;height:auto;display:block}.pat{font-size:12.5px;margin:6px 0 0;padding-left:18px}
table{border-collapse:collapse;width:100%;font-size:13px}th,td{padding:5px 6px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}
th{color:var(--mut);font-weight:500;font-size:12px}td.n{text-align:right;font-variant-numeric:tabular-nums}.scroll{overflow-x:auto}
.bar{height:6px;border-radius:3px;background:var(--chip);position:relative;min-width:80px}.bar i{position:absolute;top:0;bottom:0;left:50%;border-radius:3px}
.note{background:var(--chip);border-left:3px solid var(--warn);border-radius:6px;padding:8px 10px;font-size:12.5px;margin:0 0 10px}
.grid{display:grid;gap:10px;grid-template-columns:repeat(auto-fill,minmax(280px,1fr))}
.card{background:var(--bg);border:1px solid var(--line);border-radius:8px;padding:10px}.card.good{border-color:var(--up)}.card.stale{opacity:.6}
.head{display:flex;justify-content:space-between;align-items:baseline;gap:8px}.sym{font-weight:650;font-size:15px}.side{font-weight:700}
.levels{display:grid;grid-template-columns:repeat(3,1fr);gap:5px;margin:8px 0;font-variant-numeric:tabular-nums}
.levels div{background:var(--chip);border-radius:5px;padding:4px 6px}.levels b{display:block;font-size:10.5px;font-weight:500;color:var(--mut);text-transform:uppercase}
.verdict{border-radius:6px;padding:5px 7px;margin:6px 0;font-size:12.5px;background:var(--chip)}.verdict.good{background:var(--good)}.verdict.none{background:var(--none)}
details summary{cursor:pointer;font-weight:600;padding:6px 0}h2.sub{font-size:13px;margin:14px 0 6px}
@media(max-width:600px){.wide{display:none}header{flex-wrap:wrap}}
footer{color:var(--mut);font-size:12px;max-width:1500px;margin:0 auto;padding:0 16px 24px}
"""


def _e(v) -> str:
    return html.escape("" if v is None else str(v))


def _pct(v) -> str:
    return "–" if v is None else f"{v:+.2f}%"


def _heat_color(v: float | None) -> str:
    if v is None:
        return "#6b7480"
    x = max(-3.0, min(3.0, v)) / 3.0
    return f"hsl({140 if x >= 0 else 355} {35 + 40 * abs(x):.0f}% {38 - 8 * abs(x):.0f}%)"


def _market(rows: list[dict]) -> str:
    if not rows:
        return "<p class='mut'>Brak danych.</p>"
    parts = []
    for cat, title in CATS.items():
        tiles = [r for r in rows if r["category"] == cat]
        if not tiles:
            continue
        tiles.sort(key=lambda r: -(r["d1"] if r["d1"] is not None else -99))
        parts.append(f"<div class='cat'>{title}</div><div class='heat'>" + "".join(
            f"<div class='tile' style='background:{_heat_color(r['d1'])}' title='{_e(r['name'])}: 1 d {_pct(r['d1'])}, 5 d {_pct(r['d5'])}, 20 d {_pct(r['d20'])}'>"
            f"<b>{_e(r['symbol'])}</b><span>{_pct(r['d1'])}</span><br><span>5 d {_pct(r['d5'])}</span></div>" for r in tiles) + "</div>")
    return "".join(parts)


def _charts(charts: list[dict]) -> str:
    if not charts:
        return "<p class='mut'>Wykresy pojawią się po pierwszym przebiegu z modułem formacji.</p>"
    tabs, bodies = [], []
    for i, c in enumerate(charts):
        key = f"c{i}"
        tabs.append(f"<button type='button' data-k='{key}' aria-pressed='{str(i == 0).lower()}'>{_e(c['symbol'])} <span class='mut'>{_e(c['interval'])}</span></button>")
        pats = "".join(
            f"<li><b class='{'up' if p.get('direction', 0) > 0 else 'down' if p.get('direction', 0) < 0 else ''}'>{_e(p.get('label'))}</b>"
            f" <span class='mut'>({_e(p.get('status', ''))})</span> {_e(p.get('note', ''))}</li>" for p in c.get("patterns", []))
        bodies.append(f"<div class='chart' data-k='{key}' {'hidden' if i else ''}>{c['svg']}"
                      f"<ul class='pat'>{pats or '<li class=mut>Brak wyraźnych formacji.</li>'}</ul></div>")
    return (f"<div class='tabs' role='group'>{''.join(tabs)}</div>{''.join(bodies)}"
            "<p class='small mut'>Formacje wykrywane automatycznie na zamkniętych świecach. Ich skuteczność nie była walidowana: "
            "to opis wykresu, nie sygnał.</p>")


def _predictions(pred: dict | None) -> str:
    if not pred or not pred.get("items"):
        return "<p class='mut'>Model jeszcze nie opublikował prognoz.</p>"
    q = pred.get("quality") or {}
    skill = q.get("verdict") or "nieznana"
    note = (f"<div class='note'><b>Jakość modelu na danych testowych: {_e(skill)}.</b> {_e(q.get('text', ''))} "
            "Prawdopodobieństwo to wynik modelu; jeśli jakość jest „brak”, liczby nie są lepsze od częstości historycznej.</div>")
    rows = sorted(pred["items"], key=lambda r: -abs((r.get("p_up") or 0.5) - (r.get("base_rate") or 0.5)))
    body = "".join(
        f"<tr><td><b>{_e(r['symbol'])}</b></td><td class='n'>{_e(r.get('horizon'))} sesji</td>"
        f"<td class='n {'up' if (r.get('p_up') or 0) > (r.get('base_rate') or 0.5) else 'down'}'>{100 * (r.get('p_up') or 0):.0f}%</td>"
        f"<td class='n mut'>{100 * (r.get('base_rate') or 0):.0f}%</td>"
        f"<td><div class='bar'><i style='{_bar(r)}'></i></div></td><td class='mut'>{_e(r.get('skill'))}</td></tr>" for r in rows[:40])
    return (note + "<div class='scroll'><table><thead><tr><th>Instrument</th><th>Horyzont</th><th>Szansa wzrostu</th>"
            "<th>Częstość hist.</th><th>Różnica</th><th>Jakość</th></tr></thead><tbody>" + body + "</tbody></table></div>")


def _bar(r: dict) -> str:
    d = (r.get("p_up") or 0.5) - (r.get("base_rate") or 0.5)
    w = min(50.0, abs(d) * 250)
    return (f"left:50%;width:{w:.0f}%;background:var(--up)" if d >= 0 else f"left:{50 - w:.0f}%;width:{w:.0f}%;background:var(--down)")


def _news_static(news: list[dict]) -> str:
    items = "".join(
        f"<li><time>{_e((n.get('fetched') or '')[11:16])}</time><div><span class='imp i{n.get('importance') or 1}'></span>"
        f"<a href='{_e(n.get('url'))}' target='_blank' rel='noopener'>{_e(n.get('title'))}</a>"
        f"<div class='chips'>{''.join(f'<span class=chip>{_e(s)}</span>' for s in (n.get('symbols') or '').split(',') if s)}</div></div><span></span></li>"
        for n in news)
    return items or "<li class='mut'>Brak newsów.</li>"


def render(snap: dict, sections: dict[str, str], live_url: str | None) -> str:
    """Sklada strone. `sections`: gotowe fragmenty HTML ze starszego ekranu (sygnaly, trend miesieczny, spolki, kalendarz)."""
    gen = datetime.fromisoformat(snap["generated"])
    news0 = [{"title": n.get("title"), "url": n.get("url"), "source": n.get("source") or "", "importance": n.get("importance") or 1,
              "time": (n.get("fetched") or "").replace(" ", "T") + "Z" if n.get("fetched") else None,
              "symbols": [x for x in (n.get("symbols") or "").split(",") if x], "moved": None} for n in (snap.get("news") or [])]
    initial_live = {"generated": snap["generated"], "quotes": snap.get("quotes") or {}, "news": news0}
    return f"""<!doctype html><html lang="pl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Analizator: centrum dowodzenia</title>
<link rel="manifest" href="manifest.webmanifest"><link rel="icon" href="icon.svg" type="image/svg+xml">
<link rel="apple-touch-icon" href="apple-touch-icon.png"><meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-title" content="Analizator"><meta name="theme-color" content="#0b0f14">
<style>{CSS}</style></head><body>
<header><h1>Analizator<span class="wide"> · centrum dowodzenia</span></h1><div class="small mut"><span id="dot" class="dot"></span><span id="livestat">na żywo: łączenie…</span>
 · strona {gen:%Y-%m-%d %H:%M} UTC<span id="age"></span></div></header>
<div class="tape" aria-label="Notowania"><div class="row" id="tape"></div></div>
<div class="ticker" aria-label="Najnowsze newsy"><div class="row" id="ticker"></div></div>
<main><div id="offline" class="note" hidden>Brak połączenia: to ostatnia zapisana kopia.</div>
<div class="layout">
<section class="panel w5"><h2>Świat teraz <small id="newscount"></small></h2>
<div id="topics" class="chips" style="margin:0 0 8px"></div><ul class="news" id="news">{_news_static(snap.get('news') or [])}</ul>
<p class="small mut">Kolor: czerwony pilne, żółty istotne. Po prawej ruch ceny pierwszego instrumentu od publikacji (notowania opóźnione).</p></section>
<section class="panel w7"><h2>Mapa rynku <small>zmiana dzienna, najedź po 5 i 20 dni</small></h2>{_market(snap.get('market') or [])}</section>
<section class="panel w7"><h2>Wykresy i formacje</h2>{_charts(snap.get('charts') or [])}</section>
<section class="panel w5"><h2>Prognozy modelu</h2>{_predictions(snap.get('predictions'))}</section>
<section class="panel w12">{sections.get('monthly', '')}</section>
<section class="panel w12"><h2>Sygnały strategii <small>{len(snap.get('signals') or [])} z ostatnich świec</small></h2>{sections.get('signals', '')}</section>
<section class="panel w6">{sections.get('stocks', '')}</section>
<section class="panel w6"><h2>Kalendarz makro <small>48 h, czas UTC</small></h2>{sections.get('macro', '')}</section>
</div></main>
<footer>Program nie składa zleceń i nie zna kwotowań XTB. Ceny z darmowych, opóźnionych źródeł (kontrakty futures lub indeksy): poziomy przenoś do xStation jako odległość od ceny.
Prognozy i formacje to wyniki modeli i reguł, nie rekomendacje.{(' Statystyki walidacji z ' + _e(snap['stats_date']) + '.') if snap.get('stats_date') else ''}</footer>
<script>
const LIVE_URL = {json.dumps(live_url)}, INITIAL = {json.dumps(initial_live, ensure_ascii=False, default=str)};
if ("serviceWorker" in navigator && location.protocol.startsWith("http")) navigator.serviceWorker.register("sw.js");
const $ = (id) => document.getElementById(id), esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({{"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}})[c]);
const off = $("offline"), sync = () => {{ off.hidden = navigator.onLine; }}; addEventListener("online", sync); addEventListener("offline", sync); sync();
const gen = new Date("{gen.isoformat()}"), ago = (d) => {{ const m = Math.round((Date.now() - d) / 60000); return m < 90 ? `${{m}} min temu` : m < 2880 ? `${{Math.round(m / 60)}} h temu` : `${{Math.round(m / 1440)}} dni temu`; }};
$("age").textContent = " (" + ago(gen) + ")";
document.querySelectorAll(".tabs button").forEach((b) => b.addEventListener("click", () => {{
  document.querySelectorAll(".tabs button").forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
  document.querySelectorAll(".chart").forEach((c) => {{ c.hidden = c.dataset.k !== b.dataset.k; }});
}}));
function spark(v) {{
  if (!v || v.length < 2) return "";
  const lo = Math.min(...v), hi = Math.max(...v), r = hi - lo || 1, w = 54, h = 16;
  const pts = v.map((x, i) => `${{(i / (v.length - 1) * w).toFixed(1)}},${{(h - (x - lo) / r * h).toFixed(1)}}`).join(" ");
  return `<svg width="${{w}}" height="${{h}}" viewBox="0 0 ${{w}} ${{h}}" style="vertical-align:-3px;margin-left:6px"><polyline fill="none" stroke="${{v[v.length-1] >= v[0] ? "var(--up)" : "var(--down)"}}" stroke-width="1.4" points="${{pts}}"/></svg>`;
}}
const fmt = (p) => p >= 1000 ? p.toLocaleString("pl-PL", {{maximumFractionDigits: 0}}) : p >= 10 ? p.toFixed(2) : p.toFixed(4);
function render(live) {{
  const q = Object.entries(live.quotes || {{}});
  if (q.length) {{
    const cells = q.map(([s, x]) => `<span class="q"><b>${{esc(s)}}</b><span>${{fmt(x.price)}}</span> <span class="${{x.change_pct >= 0 ? "up" : "down"}}">${{x.change_pct >= 0 ? "▲" : "▼"}} ${{Math.abs(x.change_pct).toFixed(2)}}%</span>${{spark(x.spark)}}</span>`).join("");
    $("tape").innerHTML = cells + cells;
  }}
  const n = live.news || [];
  if (n.length) {{
    const top = n.filter((x) => x.importance >= 2).slice(0, 15);
    const t = (top.length ? top : n.slice(0, 15)).map((x) => `<span><span class="imp i${{x.importance}}"></span>${{esc(x.title)}} <span class="mut">${{esc((x.symbols || []).slice(0, 3).join(", "))}}</span></span>`).join("");
    $("ticker").innerHTML = t + t;
    $("news").innerHTML = n.slice(0, 60).map((x) => {{
      const d = x.time ? new Date(x.time) : null, mv = x.moved;
      const mvs = mv ? `<span class="${{mv.pct >= 0 ? "up" : "down"}}">${{esc(mv.symbol)}} ${{mv.pct >= 0 ? "+" : ""}}${{mv.pct.toFixed(2)}}%</span>` : "";
      return `<li><time title="${{d ? d.toISOString() : ""}}">${{d ? d.toLocaleTimeString("pl-PL", {{hour: "2-digit", minute: "2-digit"}}) : ""}}</time>
        <div><span class="imp i${{x.importance}}"></span><a href="${{esc(x.url)}}" target="_blank" rel="noopener">${{esc(x.title)}}</a>
        <div class="chips">${{(x.symbols || []).slice(0, 5).map((s) => `<span class="chip">${{esc(s)}}</span>`).join("")}}${{x.source ? `<span class="chip">${{esc(x.source)}}</span>` : ""}}</div></div>
        <span class="mv">${{mvs}}</span></li>`;
    }}).join("");
    $("newscount").textContent = `${{n.length}} z 24 h`;
    // Tematy: ile istotnych newsow dotyczy instrumentu i jak ruszyla sie jego cena (od najstarszego newsa).
    const agg = {{}};
    n.filter((x) => x.importance >= 2).forEach((x) => (x.symbols || []).slice(0, 3).forEach((s) => {{
      const a = agg[s] || (agg[s] = {{n: 0, mv: null}}); a.n += 1; if (x.moved && x.moved.symbol === s) a.mv = x.moved.pct;
    }}));
    $("topics").innerHTML = Object.entries(agg).sort((a, b) => b[1].n - a[1].n).slice(0, 10).map(([s, a]) =>
      `<span class="chip" title="istotnych newsów: ${{a.n}}"><b>${{esc(s)}}</b> ×${{a.n}}${{a.mv == null ? "" : ` <span class="${{a.mv >= 0 ? "up" : "down"}}">${{a.mv >= 0 ? "+" : ""}}${{a.mv.toFixed(1)}}%</span>`}}</span>`).join("");
  }}
  const g = new Date(live.generated), fresh = Date.now() - g < 15 * 60000;
  $("dot").className = "dot" + (fresh ? " on" : "");
  $("livestat").textContent = "na żywo: " + ago(g);
}}
render(INITIAL);
async function poll() {{
  if (!LIVE_URL) return;
  try {{
    const r = await fetch(LIVE_URL + "?t=" + Math.floor(Date.now() / 60000), {{cache: "no-store"}});
    if (r.ok) render(await r.json());
  }} catch (e) {{ $("livestat").textContent = "na żywo: brak połączenia"; }}
}}
poll(); setInterval(poll, 120000);
</script></body></html>"""
