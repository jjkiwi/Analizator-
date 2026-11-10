"""Statyczny panel HTML generowany z bazy. Bez serwera: plik mozna otworzyc w przegladarce lub na telefonie."""
from __future__ import annotations

import html
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from . import journal

CSS = """
:root{--bg:#f6f8fa;--card:#fff;--fg:#1f2328;--mut:#656d76;--line:#d0d7de;--up:#1a7f37;--down:#cf222e;--warn:#9a6700}
@media(prefers-color-scheme:dark){:root{--bg:#0d1117;--card:#161b22;--fg:#e6edf3;--mut:#8b949e;--line:#30363d;--up:#3fb950;--down:#f85149;--warn:#d29922}}
*{box-sizing:border-box}body{margin:0;padding:16px;background:var(--bg);color:var(--fg);font:14px/1.45 system-ui,sans-serif}
h1{font-size:20px;margin:0 0 4px}h2{font-size:15px;margin:0 0 8px}.mut{color:var(--mut)}
.grid{display:grid;gap:12px;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));margin-top:12px}
.card{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:12px;overflow-x:auto}
table{border-collapse:collapse;width:100%}th,td{padding:4px 6px;border-bottom:1px solid var(--line);text-align:left;white-space:nowrap}
th{color:var(--mut);font-weight:500}td.wrap{white-space:normal}.up{color:var(--up)}.down{color:var(--down)}.warn{color:var(--warn)}
"""


def _e(v) -> str:
    return html.escape("" if v is None else str(v))


def _table(headers: list[str], rows: list[list[str]], empty: str) -> str:
    if not rows:
        return f"<p class='mut'>{_e(empty)}</p>"
    head = "".join(f"<th>{_e(h)}</th>" for h in headers)
    body = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def _side(side: int) -> str:
    return "<span class='up'>LONG</span>" if side > 0 else "<span class='down'>SHORT</span>"


def render(conn: sqlite3.Connection) -> str:
    signals = [[_e(r["time"][:16].replace("T", " ")), _e(r["symbol"]), _side(r["side"]), _e(r["strategy"]), _e(r["interval"]),
                f"{r['ref_price']:.5g}", f"{r['stop_loss']:.5g}", f"{r['take_profit']:.5g}",
                _e(json.loads(r["context"] or "{}").get("label", "")), _e(r["status"]),
                "" if r["r_result"] is None else f"<span class='{'up' if r['r_result'] > 0 else 'down'}'>{r['r_result']:+.2f}R</span>"]
               for r in journal.recent(conn, 40)]
    stats = [[_e(s["strategy"]), _e(s["interval"]), str(s["total"]), str(s["resolved"] or 0), str(s["wins"] or 0),
              "–" if s["expectancy_r"] is None else f"{s['expectancy_r']:+.2f}R", "–" if s["total_r"] is None else f"{s['total_r']:+.1f}R"]
             for s in journal.stats(conn)]
    news = [[_e((r["published"] or r["fetched"])[:16].replace("T", " ")), "🔴" if r["importance"] >= 3 else "🟡", _e(r["symbols"]),
             f"<span class='wrap'>{_e(r['title'])}</span>"]
            for r in conn.execute("SELECT * FROM news WHERE importance >= 2 ORDER BY fetched DESC LIMIT 25")]
    now = datetime.now(timezone.utc).isoformat()
    macro = [[_e(r["time"][:16].replace("T", " ")), _e(r["country"]), _e(r["name"]), "●" * (r["importance"] or 1),
              _e(r["forecast"]), _e(r["previous"])]
             for r in conn.execute("SELECT * FROM macro_events WHERE time >= ? AND importance >= 2 ORDER BY time LIMIT 25", (now,))]
    bias = [[_e(r["symbol"]), f"<span class='{'up' if r['bias'] > 0.15 else 'down' if r['bias'] < -0.15 else 'mut'}'>{r['bias']:+.2f}</span>",
             _e(r["updated"][:10])] for r in conn.execute("SELECT * FROM fundamental_bias ORDER BY bias DESC")]
    health = [[_e(r["source"]), f"<span class='warn'>błąd ×{r['fail_streak']}</span>", f"<span class='wrap'>{_e((r['last_error'] or '')[:90])}</span>"]
              for r in conn.execute("SELECT * FROM source_health WHERE fail_streak > 0 ORDER BY fail_streak DESC LIMIT 20")]
    cards = [
        ("Sygnały", _table(["Czas (UTC)", "Instrument", "Kier.", "Strategia", "Int.", "Cena", "SL", "TP", "Zgodność", "Status", "Wynik"], signals, "Brak sygnałów.")),
        ("Skuteczność na żywo", _table(["Strategia", "Int.", "Sygnałów", "Rozlicz.", "Wygr.", "Oczek.", "Suma"], stats, "Dziennik jest pusty.")),
        ("Newsy (waga ≥ 2)", _table(["Czas (UTC)", "", "Instrumenty", "Tytuł"], news, "Brak newsów.")),
        ("Kalendarz makro", _table(["Czas (UTC)", "Kraj", "Wydarzenie", "Waga", "Prognoza", "Poprz."], macro, "Brak wydarzeń. Uruchom `cfd macro refresh`.")),
        ("Bias fundamentalny", _table(["Instrument", "Bias (−2..+2)", "Aktualizacja"], bias, "Brak danych. Wymaga FRED_API_KEY i `cfd bias update`.")),
        ("Problemy ze źródłami", _table(["Źródło", "Stan", "Ostatni błąd"], health, "Wszystkie źródła działają.")),
    ]
    body = "".join(f"<section class='card'><h2>{_e(t)}</h2>{c}</section>" for t, c in cards)
    return (f"<!doctype html><html lang='pl'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width, initial-scale=1'>"
            f"<title>Analizator CFD</title><style>{CSS}</style></head><body><h1>Analizator CFD</h1>"
            f"<div class='mut'>Stan na {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC. Ceny ze źródeł danych, nie z XTB.</div>"
            f"<div class='grid'>{body}</div></body></html>")


def write(conn: sqlite3.Connection, path: Path | str = "reports/panel.html") -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render(conn), encoding="utf-8")
    return path
