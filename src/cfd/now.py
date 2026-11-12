"""Ekran "stan na teraz": sygnaly z ostatnich zamknietych swiec razem ze zmierzona skutecznoscia.

Zasada: przy sygnale stoi to, co wyszlo w walidacji na danych niewidzianych przy doborze parametrow
(liczba transakcji, odsetek zyskownych, sredni wynik po kosztach), a nie obietnica. Gdy przewagi nie ma
albo proba jest za mala, ekran mowi to wprost. Program nie sklada zlecen.
"""
from __future__ import annotations

import html
import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

from .data import DataSourceError
from .data.quality import STEP
from .fundamentals import read_bias
from .scanner import latest_signal
from .strategies import REGISTRY
from .validation.context import evaluate, label_trades

MIN_TRADES = 30
FEATURE_NAMES = {"regime": "reżim", "d1_trend": "trend dzienny", "vol": "zmienność", "session": "sesja", "vix": "VIX", "bias": "bias fundamentalny"}
VALUE_NAMES = {
    "z_trendem": "z trendem", "pod_trend": "pod trend", "konsolidacja": "konsolidacja", "mieszany": "mieszany",
    "zgodny": "zgodny", "przeciwny": "przeciwny", "neutralny": "neutralny", "wysoka": "wysoka", "niska": "niska",
    "srednia": "średnia", "wysoki": "wysoki", "niski": "niski", "europa": "Europa", "usa": "USA", "azja": "Azja",
    "dzienny": "–", "brak": "brak danych",
}


def load_stats(reports_dir: Path | str = "reports") -> dict[tuple[str, str, str], dict]:
    """Wyniki walk-forward z raportow JSON: (symbol, strategia, interwal) -> wiersz. Raporty kosztow x2 pomijane."""
    out: dict[tuple[str, str, str], dict] = {}
    for path in sorted(Path(reports_dir).glob("**/walidacja_*.json")):
        if "koszty" in path.name:
            continue
        for row in json.loads(path.read_text(encoding="utf-8")):
            if "error" not in row:
                out[(row["symbol"], row["strategy"], row["interval"])] = row
    return out


def load_confirmed_filters(reports_dir: Path | str = "reports") -> list[dict]:
    """Filtry kontekstowe potwierdzone na probie niewidzianej (wynik `cfd context-test`). Brak pliku = brak filtrow."""
    path = Path(reports_dir) / "kontekst_transakcje.parquet"
    if not path.exists():
        return []
    cells, _ = evaluate(pd.read_parquet(path))
    return [
        {"interval": c.interval, "strategy": c.strategy, "scope": c.scope, "feature": c.feature, "value": c.value,
         "n": c.n_c, "mean_r": c.mean_c}
        for c in cells if c.confirmed
    ]


def assess(stats: dict | None) -> tuple[str, str]:
    """(klasa, opis) dla zmierzonej skutecznosci sygnalu. Klasy: good, weak, none, unknown."""
    if not stats or not stats.get("folds"):
        return "unknown", "brak walidacji (za krótka historia)"
    n = stats.get("trades") or 0
    if n < MIN_TRADES:
        return "unknown", f"za mało danych ({n} transakcji w walidacji)"
    if (stats.get("expectancy_r") or 0) <= 0:
        return "none", "brak przewagi po kosztach"
    if stats.get("verdict") == "pass":
        return "good", "dodatni wynik w walidacji (niepotwierdzony na drugim interwale)"
    return "weak", "wynik dodatni, ale niestabilny"


def _context_for(sig_side: int, df: pd.DataFrame, daily: pd.DataFrame, interval: str, vix: pd.Series | None,
                 bias: float | None) -> dict[str, str]:
    """Kontekst biezacego sygnalu: te same etykiety co w tescie, liczone na zamknietych swiecach."""
    one = pd.DataFrame({"entry_time": [df.index[-1]], "side": [sig_side], "r": [0.0]})
    row = label_trades(one, df, daily, interval, vix, None).iloc[0]
    ctx = {f: row[f] for f in ("regime", "d1_trend", "vol", "session", "vix")}
    ctx["bias"] = "brak" if bias is None else "zgodny" if bias * sig_side >= 0.5 else "przeciwny" if bias * sig_side <= -0.5 else "neutralny"
    return ctx


def build_snapshot(instruments: dict, data_service, conn: sqlite3.Connection, intervals: list[str], strategies: list[str],
                   stats: dict, filters: list[dict], refresh: bool = True, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    vix = None
    if "VIX" in instruments:
        try:
            vix = data_service.get(instruments["VIX"], "1d")["close"]
        except DataSourceError:
            pass
    signals, errors, scanned = [], [], 0
    for inst in instruments.values():
        if not inst.sources:
            continue
        bias = read_bias(conn, inst.symbol)
        daily = None
        for interval in intervals:
            try:
                df = data_service.get(inst, interval, refresh=refresh)
                if daily is None:
                    daily = df if interval == "1d" else data_service.get(inst, "1d", refresh=refresh)
            except DataSourceError as exc:
                errors.append(f"{inst.symbol} {interval}: {str(exc)[:80]}")
                continue
            scanned += 1
            if len(df) < 3:
                continue
            closed_at = df.index[-2] + STEP[interval]
            live = df.iloc[-1]
            for name in strategies:
                sig = latest_signal(inst, REGISTRY[name](), df)
                if sig is None:
                    continue
                hit = None  # czy od zamkniecia swiecy cena dotknela juz SL albo TP
                lo, hi = float(live["low"]), float(live["high"])
                sl_hit = lo <= sig.stop_loss if sig.side > 0 else hi >= sig.stop_loss
                tp_hit = hi >= sig.take_profit if sig.side > 0 else lo <= sig.take_profit
                if sl_hit or tp_hit:
                    hit = "SL" if sl_hit else "TP"
                ctx = _context_for(sig.side, df, daily, interval, vix, bias)
                st = stats.get((inst.symbol, name, interval))
                cls, text = assess(st)
                matched = [
                    f for f in filters
                    if f["interval"] == interval and f["strategy"] == name and f["scope"] in ("wszystkie", inst.category)
                    and ctx.get(f["feature"]) == f["value"]
                ]
                risk = abs(sig.ref_price - sig.stop_loss)
                signals.append({
                    "symbol": inst.symbol, "name": inst.name, "category": inst.category, "interval": interval, "strategy": name,
                    "side": sig.side, "candle_time": sig.time.isoformat(), "closed_at": closed_at.isoformat(),
                    "age_minutes": round((pd.Timestamp(now) - closed_at).total_seconds() / 60),
                    "ref_price": sig.ref_price, "last_price": float(live["close"]), "stop_loss": sig.stop_loss,
                    "take_profit": sig.take_profit, "sl_pct": 100 * risk / sig.ref_price,
                    "rr": abs(sig.take_profit - sig.ref_price) / risk if risk else None,
                    "already_hit": hit, "rationale": sig.rationale, "context": ctx, "bias": bias,
                    "stats": None if not st else {k: st.get(k) for k in ("trades", "win_rate", "expectancy_r", "profit_factor", "verdict", "folds")},
                    "assessment": cls, "assessment_text": text, "filters": matched,
                })
    order = {"good": 0, "weak": 1, "unknown": 2, "none": 3}
    signals.sort(key=lambda s: (not s["filters"], order[s["assessment"]], s["already_hit"] is not None, s["symbol"]))
    macro = [dict(r) for r in conn.execute(
        "SELECT time, country, name, importance, forecast, previous FROM macro_events "
        "WHERE time >= ? AND time <= ? AND importance >= 2 ORDER BY time LIMIT 15",
        (now.isoformat(), (now + timedelta(days=2)).isoformat()))]
    news = [dict(r) for r in conn.execute(
        "SELECT fetched, title, symbols, importance, url FROM news WHERE importance >= 2 ORDER BY fetched DESC LIMIT 12")]
    return {"generated": now.isoformat(), "intervals": intervals, "scanned": scanned, "signals": signals,
            "errors": errors, "macro": macro, "news": news, "filters": filters}


# ---------- HTML ----------

CSS = """
:root{--bg:#f4f5f7;--card:#fff;--fg:#1b1f24;--mut:#5f6873;--line:#d5dae0;--up:#17713a;--down:#c0262d;--warn:#8a5a00;--chip:#eef1f4;--good:#e3f4e8;--none:#f7e9ea}
@media(prefers-color-scheme:dark){:root{--bg:#0e1116;--card:#171b21;--fg:#e7ebf0;--mut:#8d96a1;--line:#2c333c;--up:#4cc26a;--down:#f0606a;--warn:#d9a13a;--chip:#222830;--good:#16301f;--none:#33191c}}
*{box-sizing:border-box}body{margin:0;padding:16px;background:var(--bg);color:var(--fg);font:15px/1.45 system-ui,-apple-system,"Segoe UI",sans-serif}
main{max-width:980px;margin:0 auto}h1{font-size:22px;margin:0}h2{font-size:16px;margin:24px 0 8px}
.mut{color:var(--mut)}.small{font-size:13px}.up{color:var(--up)}.down{color:var(--down)}.warn{color:var(--warn)}
.note{background:var(--card);border:1px solid var(--line);border-left:4px solid var(--warn);border-radius:8px;padding:10px 12px;margin:12px 0}
.grid{display:grid;gap:12px;grid-template-columns:repeat(auto-fill,minmax(300px,1fr))}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px}
.card.good{border-color:var(--up)}.card.stale{opacity:.6}
.head{display:flex;justify-content:space-between;align-items:baseline;gap:8px}.sym{font-weight:650;font-size:17px}
.side{font-weight:700;letter-spacing:.03em}.levels{display:grid;grid-template-columns:repeat(3,1fr);gap:6px;margin:10px 0;font-variant-numeric:tabular-nums}
.levels div{background:var(--chip);border-radius:6px;padding:6px 8px}.levels b{display:block;font-size:11px;font-weight:500;color:var(--mut);text-transform:uppercase;letter-spacing:.04em}
.verdict{border-radius:6px;padding:6px 8px;margin:8px 0;font-size:14px;background:var(--chip)}
.verdict.good{background:var(--good)}.verdict.none{background:var(--none)}
.chips{display:flex;flex-wrap:wrap;gap:4px;margin-top:6px}.chip{background:var(--chip);border-radius:999px;padding:2px 8px;font-size:12px;color:var(--mut)}
.chip.ok{color:var(--up)}.chip.bad{color:var(--down)}
table{border-collapse:collapse;width:100%;font-size:14px}th,td{padding:5px 6px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}
th{color:var(--mut);font-weight:500}.scroll{overflow-x:auto}details{margin-top:12px}summary{cursor:pointer;font-weight:600;padding:6px 0}
a{color:inherit}
"""


def _e(v) -> str:
    return html.escape("" if v is None else str(v))


def _num(v: float) -> str:
    if v is None:
        return "–"
    a = abs(v)
    return f"{v:,.0f}".replace(",", " ") if a >= 10000 else f"{v:.2f}" if a >= 100 else f"{v:.3f}" if a >= 1 else f"{v:.5f}"


def _age(minutes: int) -> str:
    return f"{minutes} min temu" if minutes < 90 else f"{minutes / 60:.0f} h temu" if minutes < 2880 else f"{minutes / 1440:.0f} dni temu"


def _card(s: dict) -> str:
    side = "<span class='side up'>KUP (LONG)</span>" if s["side"] > 0 else "<span class='side down'>SPRZEDAJ (SHORT)</span>"
    st = s["stats"]
    if st and st.get("trades"):
        measured = (f"W walidacji: {st['trades']} transakcji, zyskownych {st['win_rate']:.0%}, "
                    f"średnio {st['expectancy_r']:+.2f} R po kosztach.")
    else:
        measured = "Brak zmierzonej skuteczności."
    stale = f"<div class='warn small'>Od zamknięcia świecy cena dotknęła już poziomu {s['already_hit']}: sygnał nieaktualny.</div>" if s["already_hit"] else ""
    filt = "".join(
        f"<div class='verdict good'>Sprzyjający kontekst potwierdzony na danych niewidzianych: {_e(FEATURE_NAMES[f['feature']])} = "
        f"{_e(VALUE_NAMES.get(f['value'], f['value']))} ({f['n']} transakcji, średnio {f['mean_r']:+.2f} R).</div>" for f in s["filters"])
    chips = []
    for key in ("regime", "d1_trend", "bias", "vol", "vix", "session"):
        val = s["context"].get(key, "brak")
        if val in ("brak", "dzienny"):
            continue
        cls = " ok" if val in ("z_trendem", "zgodny") else " bad" if val in ("pod_trend", "przeciwny") else ""
        chips.append(f"<span class='chip{cls}'>{_e(FEATURE_NAMES[key])}: {_e(VALUE_NAMES.get(val, val))}</span>")
    rr = f"{s['rr']:.1f}" if s["rr"] else "–"
    card_cls = "card" + (" good" if s["filters"] else "") + (" stale" if s["already_hit"] else "")
    return f"""<div class="{card_cls}">
<div class="head"><span class="sym">{_e(s['symbol'])} <span class="mut small">{_e(s['name'])}</span></span><span class="mut small">{_e(s['interval'])}</span></div>
<div>{side} <span class="mut small">· {_e(s['strategy'])} · świeca zamknięta {_age(s['age_minutes'])}</span></div>
<div class="levels"><div><b>Cena sygnału</b>{_num(s['ref_price'])}</div><div><b>Stop loss</b>{_num(s['stop_loss'])}</div><div><b>Take profit</b>{_num(s['take_profit'])}</div></div>
<div class="small mut">Teraz {_num(s['last_price'])} · SL {s['sl_pct']:.2f}% od ceny · zysk do ryzyka {rr}</div>
{stale}{filt}<div class="verdict {s['assessment']}"><b>{_e(s['assessment_text'].capitalize())}.</b> {measured}</div>
<div class="small mut">{_e(s['rationale'])}</div><div class="chips">{''.join(chips)}</div></div>"""


def render_html(snap: dict) -> str:
    gen = datetime.fromisoformat(snap["generated"])
    sigs = snap["signals"]
    top = [s for s in sigs if s["filters"] or s["assessment"] == "good"]
    mid = [s for s in sigs if s not in top and s["assessment"] in ("weak", "unknown")]
    rest = [s for s in sigs if s["assessment"] == "none" and not s["filters"]]
    if top:
        lead = f"<h2>Sygnały z dodatnim wynikiem w walidacji ({len(top)})</h2><div class='grid'>{''.join(_card(s) for s in top)}</div>"
    else:
        lead = ("<h2>Sygnały z dodatnim wynikiem w walidacji</h2><p class='mut'>Teraz żadnego. To normalny stan: "
                "program pokazuje tu tylko sygnały, które w testach na niewidzianych danych zarabiały po kosztach.</p>")
    mid_html = f"<details><summary>Niepewne: słaby wynik albo za mało danych ({len(mid)})</summary><div class='grid'>{''.join(_card(s) for s in mid)}</div></details>" if mid else ""
    rest_html = f"<details><summary>Bez przewagi po kosztach ({len(rest)})</summary><div class='grid'>{''.join(_card(s) for s in rest)}</div></details>" if rest else ""
    macro_rows = "".join(
        f"<tr><td>{_e(m['time'][5:16].replace('T', ' '))}</td><td>{_e(m['country'])}</td><td>{_e(m['name'])}</td><td>{_e(m['forecast'] or '–')}</td><td>{_e(m['previous'] or '–')}</td></tr>"
        for m in snap["macro"])
    macro = f"<div class='scroll'><table><thead><tr><th>Czas (UTC)</th><th>Kraj</th><th>Wydarzenie</th><th>Prognoza</th><th>Poprzednio</th></tr></thead><tbody>{macro_rows}</tbody></table></div>" if macro_rows else "<p class='mut'>Brak danych. Uruchom <code>cfd macro refresh</code>.</p>"
    news_rows = "".join(
        f"<tr><td>{_e((n['fetched'] or '')[5:16])}</td><td><a href='{_e(n['url'])}' rel='noopener'>{_e(n['title'])}</a></td><td class='mut'>{_e((n['symbols'] or '').replace(',', ', '))}</td></tr>"
        for n in snap["news"])
    news = f"<div class='scroll'><table><thead><tr><th>Pobrano</th><th>Tytuł</th><th>Instrumenty</th></tr></thead><tbody>{news_rows}</tbody></table></div>" if news_rows else "<p class='mut'>Brak danych. Uruchom <code>cfd news poll</code>.</p>"
    errors = f"<details><summary class='warn'>Źródła danych, które zawiodły ({len(snap['errors'])})</summary><p class='small mut'>{'<br>'.join(_e(x) for x in snap['errors'])}</p></details>" if snap["errors"] else ""
    return f"""<!doctype html><html lang="pl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Analizator CFD: stan na teraz</title><style>{CSS}</style></head><body><main>
<h1>Stan na teraz</h1>
<p class="mut small">Wygenerowano {gen:%Y-%m-%d %H:%M} UTC · interwały: {_e(', '.join(snap['intervals']))} · sprawdzonych serii: {snap['scanned']} · sygnałów: {len(sigs)}</p>
<div class="note small">Program nie składa zleceń i nie zna kwotowań XTB. Ceny pochodzą z opóźnionych, darmowych źródeł (kontrakty futures lub indeksy),
więc poziomy SL i TP przenieś do xStation jako odległość od bieżącej ceny, nie jako cenę. Liczby przy sygnale to wynik testów na danych historycznych,
których strategia nie widziała przy doborze parametrów. Nie są gwarancją wyniku.</div>
{lead}{mid_html}{rest_html}{errors}
<h2>Kalendarz makro: najbliższe 48 godzin</h2>{macro}
<h2>Ostatnie newsy (tło)</h2>{news}
</main></body></html>"""


def write(snap: dict, path: Path | str = "reports/teraz.html") -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_html(snap), encoding="utf-8")
    path.with_suffix(".json").write_text(json.dumps(snap, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    return path
