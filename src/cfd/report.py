"""Raport walidacji: macierz instrument x strategia z wynikami walk-forward (HTML + JSON)."""
from __future__ import annotations

import html
import json
from datetime import datetime, timezone
from pathlib import Path

from .strategies import PARAM_GRIDS, REGISTRY
from .validation import verdict, walk_forward


def build_rows(instruments, data_service, interval: str, strategies: list[str], train_bars: int, test_bars: int,
               progress=None) -> list[dict]:
    rows = []
    for inst in instruments:
        try:
            df = data_service.get(inst, interval)
        except Exception as exc:
            rows.append({"symbol": inst.symbol, "category": inst.category, "error": str(exc)[:120]})
            continue
        for name in strategies:
            res = walk_forward(df, REGISTRY[name], PARAM_GRIDS.get(name, {}), inst.costs, train_bars, test_bars)
            st = res.stats
            v, why = verdict(st, res.folds) if res.folds else ("fail", "za krotka historia na walk-forward")
            rows.append({
                "symbol": inst.symbol, "category": inst.category, "strategy": name, "interval": interval,
                "bars": len(df), "folds": len(res.folds), "trades": st.get("trades", 0),
                "win_rate": st.get("win_rate"), "expectancy_r": st.get("expectancy_r"),
                "profit_factor": st.get("profit_factor"), "total_r": st.get("total_r"),
                "costs_total_r": st.get("costs_total_r"), "max_drawdown_pct": st.get("max_drawdown_pct"),
                "verdict": v, "why": why,
            })
            if progress:
                progress(rows[-1])
    return rows


def _cell(v, fmt="{:.2f}"):
    if v is None:
        return "–"
    if isinstance(v, float):
        return "∞" if v == float("inf") else fmt.format(v)
    return html.escape(str(v))


def render_html(rows: list[dict], title: str = "Walidacja strategii (walk-forward)") -> str:
    colors = {"pass": "#1a7f37", "weak": "#9a6700", "fail": "#cf222e"}
    body = []
    for r in sorted(rows, key=lambda r: (r.get("verdict") != "pass", r.get("verdict") != "weak", -(r.get("expectancy_r") or -9))):
        if "error" in r:
            body.append(f"<tr><td>{_cell(r['symbol'])}</td><td colspan=9>brak danych: {_cell(r['error'])}</td></tr>")
            continue
        body.append(
            "<tr>"
            f"<td>{_cell(r['symbol'])}</td><td>{_cell(r['strategy'])}</td><td>{_cell(r['interval'])}</td>"
            f"<td>{_cell(r['trades'])}</td><td>{_cell(r['win_rate'], '{:.0%}')}</td>"
            f"<td>{_cell(r['expectancy_r'], '{:+.2f}')}</td><td>{_cell(r['profit_factor'])}</td>"
            f"<td>{_cell(r['total_r'], '{:+.1f}')}</td><td>{_cell(r['max_drawdown_pct'], '{:.1f}%')}</td>"
            f"<td style='color:{colors[r['verdict']]};font-weight:600'>{r['verdict'].upper()}</td>"
            f"<td>{_cell(r['why'])}</td></tr>"
        )
    n_pass = sum(r.get("verdict") == "pass" for r in rows)
    return f"""<!doctype html><html lang="pl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>{html.escape(title)}</title>
<style>body{{font:14px system-ui,sans-serif;margin:16px;color:#1f2328;background:#fff}}
.wrap{{overflow-x:auto}}table{{border-collapse:collapse;width:100%}}
th,td{{padding:6px 8px;border-bottom:1px solid #d0d7de;text-align:right;white-space:nowrap}}
th:first-child,td:first-child,td:nth-child(2),td:last-child{{text-align:left}}td:last-child{{white-space:normal}}
@media(prefers-color-scheme:dark){{body{{background:#0d1117;color:#e6edf3}}th,td{{border-color:#30363d}}}}</style></head><body>
<h1>{html.escape(title)}</h1>
<p>Wygenerowano {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC. Kombinacji: {len(rows)}, z oceną PASS: {n_pass}.
Wyniki pochodzą wyłącznie z okien testowych (dane niewidziane przy doborze parametrów), z kosztami z konfiguracji.
Im więcej kombinacji sprawdzasz, tym więcej "PASS" pojawi się przez przypadek: traktuj je jako kandydatów do forward testu.</p>
<div class="wrap"><table><thead><tr><th>Instrument</th><th>Strategia</th><th>Int.</th><th>Trans.</th><th>Skut.</th>
<th>Oczek. R</th><th>PF</th><th>Suma R</th><th>Max DD</th><th>Ocena</th><th>Uzasadnienie</th></tr></thead>
<tbody>{''.join(body)}</tbody></table></div></body></html>"""


def write_report(rows: list[dict], out_dir: Path | str = "reports", stem: str = "walidacja") -> tuple[Path, Path]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    html_path, json_path = out / f"{stem}.html", out / f"{stem}.json"
    html_path.write_text(render_html(rows), encoding="utf-8")
    json_path.write_text(json.dumps(rows, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    return html_path, json_path
