from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import yaml


def load_components(path: Path | str = "config/fundamentals.yaml") -> dict[str, list[dict]]:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))["components"]


def component_score(series: pd.Series, lookback_days: int, sign: int, min_history: int = 30) -> float | None:
    """Ostatnia zmiana serii w oknie `lookback_days`, w odchyleniach standardowych historii takich zmian.

    Wynik pomnozony przez `sign` i przyciety do [-2, 2]. None, gdy historii jest za malo.
    """
    s = series.dropna().sort_index()
    if len(s) < 3:
        return None
    daily = s.resample("1D").last().ffill()
    change = (daily - daily.shift(lookback_days)).dropna()
    if len(change) < max(min_history, lookback_days):
        return None
    sd = change.std(ddof=0)
    if not np.isfinite(sd) or sd == 0:
        return 0.0
    return float(np.clip(sign * change.iloc[-1] / sd, -2, 2))


def compute_bias(components: list[dict], get_series) -> tuple[float | None, list[dict]]:
    """Zwraca (bias w [-2, 2] albo None, szczegoly skladowych). `get_series(id)` -> pd.Series."""
    details = []
    for comp in components:
        entry = {"series": comp["series"], "label": comp.get("label", comp["series"]), "score": None}
        try:
            entry["score"] = component_score(get_series(comp["series"]), int(comp.get("lookback", 63)), int(comp.get("sign", 1)))
        except Exception as exc:  # jedna zepsuta seria nie moze wylaczyc calego biasu
            entry["error"] = str(exc)
        details.append(entry)
    scores = [d["score"] for d in details if d["score"] is not None]
    return (round(float(np.mean(scores)), 2) if scores else None), details


def save_bias(conn: sqlite3.Connection, symbol: str, bias: float, details: list[dict]) -> None:
    conn.execute(
        """INSERT INTO fundamental_bias (symbol, bias, components, updated) VALUES (?,?,?,?)
           ON CONFLICT(symbol) DO UPDATE SET bias=excluded.bias, components=excluded.components, updated=excluded.updated""",
        (symbol, bias, json.dumps(details, ensure_ascii=False), datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()


def read_bias(conn: sqlite3.Connection, symbol: str, max_age_days: float = 7.0) -> float | None:
    """Bias dla symbolu albo None, gdy go nie ma lub jest przeterminowany."""
    row = conn.execute("SELECT bias, updated FROM fundamental_bias WHERE symbol=?", (symbol,)).fetchone()
    if not row:
        return None
    age = datetime.now(timezone.utc) - datetime.fromisoformat(row["updated"])
    return row["bias"] if age.total_seconds() <= max_age_days * 86400 else None


def positioning_percentile(net_positions: pd.Series, window: int = 156) -> float | None:
    """Percentyl (0-100) biezacej pozycji netto spekulantow na tle `window` raportow COT.

    Skrajne wartosci (>90 lub <10) to sygnal przegrzania, zwykle kontrariański. Adapter danych CFTC: zadanie na pozniej.
    """
    s = net_positions.dropna().iloc[-window:]
    if len(s) < 20:
        return None
    return float((s <= s.iloc[-1]).mean() * 100)
