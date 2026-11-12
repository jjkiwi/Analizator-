from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import yaml


DEFAULT_MAX_AGE_DAYS = 45


def load_components(path: Path | str = "config/fundamentals.yaml") -> dict[str, list[dict]]:
    """Skladowe biasu per instrument. Skladowe `type: positioning` bez pola `series` dostaja je
    z sekcji `cot_contracts` (instrument -> kod kontraktu CFTC i typ raportu)."""
    cfg = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    contracts = cfg.get("cot_contracts") or {}
    max_age = cfg.get("max_age_days", DEFAULT_MAX_AGE_DAYS)
    out: dict[str, list[dict]] = {}
    for symbol, comps in cfg["components"].items():
        resolved = []
        for comp in comps:
            comp = dict(comp)
            if comp.get("type") == "positioning" and "series" not in comp:
                contract = contracts.get(symbol)
                if not contract:
                    raise ValueError(f"fundamentals.yaml: {symbol} ma skladowa positioning, ale brak wpisu w cot_contracts")
                comp["series"] = f"CFTC:{contract.get('report', 'legacy')}:{contract['code']}"
                comp.setdefault("label", f"pozycjonowanie COT ({contract.get('name', contract['code'])})")
            comp.setdefault("max_age", max_age)
            resolved.append(comp)
        out[symbol] = resolved
    return out


def component_score(series: pd.Series, lookback_days: int, sign: int, min_history: int = 30, transform: str | None = None) -> float | None:
    """Ostatnia zmiana serii w oknie `lookback_days`, w odchyleniach standardowych historii takich zmian.

    Wynik pomnozony przez `sign` i przyciety do [-2, 2]. None, gdy historii jest za malo.
    `transform="yoy"`: zamiast poziomu liczona jest roznica wobec tego samego tygodnia rok wczesniej
    (usuwa sezonowosc, np. zapasow gazu i benzyny).
    """
    s = series.dropna().sort_index()
    if len(s) < 3:
        return None
    daily = s.resample("1D").last().ffill()
    if transform == "yoy":
        daily = (daily - daily.shift(364)).dropna()
    elif transform:
        raise ValueError(f"Nieznana transformacja: {transform}")
    change = (daily - daily.shift(lookback_days)).dropna()
    if len(change) < max(min_history, lookback_days):
        return None
    sd = change.std(ddof=0)
    if not np.isfinite(sd) or sd == 0:
        return 0.0
    return float(np.clip(sign * change.iloc[-1] / sd, -2, 2))


def positioning_score(net_positions: pd.Series, window: int = 156, low: float = 10.0, high: float = 90.0, sign: int = 1) -> float | None:
    """Skladowa kontrarianska z percentyla pozycji netto spekulantow.

    W strefie neutralnej (`low`..`high`) wynik 0. Powyzej `high` (tlok po dlugiej stronie) od -1 do -2,
    ponizej `low` (tlok po krotkiej stronie) od +1 do +2, liniowo do skraju. None przy zbyt krotkiej historii.
    `sign=-1` odwraca interpretacje (podazanie za spekulantami).
    """
    pct = positioning_percentile(net_positions, window)
    if pct is None:
        return None
    if pct >= high:
        raw = -(1.0 + (pct - high) / max(100.0 - high, 1e-9))
    elif pct <= low:
        raw = 1.0 + (low - pct) / max(low, 1e-9)
    else:
        return 0.0
    return float(np.clip(sign * raw, -2, 2))


def _check_fresh(series: pd.Series, max_age_days: float, now: datetime | None) -> None:
    last = pd.Timestamp(series.dropna().index.max())
    last = last.tz_localize("UTC") if last.tzinfo is None else last.tz_convert("UTC")
    age = (pd.Timestamp(now or datetime.now(timezone.utc)) - last).days
    if age > max_age_days:
        raise ValueError(f"seria nieaktualna: ostatnia obserwacja {last.date()} ({age} dni temu)")


def compute_bias(components: list[dict], get_series, now: datetime | None = None) -> tuple[float | None, list[dict]]:
    """Zwraca (bias w [-2, 2] albo None, szczegoly skladowych). `get_series(id)` -> pd.Series.

    Typy skladowych: `change` (domyslny, zmiana serii) i `positioning` (percentyl pozycjonowania COT).
    Skladowa z polem `max_age` jest odrzucana, gdy ostatnia obserwacja jest starsza niz tyle dni.
    """
    details = []
    for comp in components:
        kind = comp.get("type", "change")
        entry = {"series": comp["series"], "label": comp.get("label", comp["series"]), "type": kind, "score": None}
        try:
            s = get_series(comp["series"])
            if comp.get("max_age") is not None:
                _check_fresh(s, float(comp["max_age"]), now)
            if kind == "positioning":
                window = int(comp.get("window", 156))
                entry["percentile"] = positioning_percentile(s, window)
                entry["score"] = positioning_score(s, window, float(comp.get("low", 10)), float(comp.get("high", 90)), int(comp.get("sign", 1)))
            elif kind == "change":
                entry["score"] = component_score(s, int(comp.get("lookback", 63)), int(comp.get("sign", 1)), transform=comp.get("transform"))
            else:
                raise ValueError(f"nieznany typ skladowej: {kind}")
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

    Skrajne wartosci (>90 lub <10) to sygnal przegrzania, zwykle kontrariański (patrz `positioning_score`).
    """
    s = net_positions.dropna().iloc[-window:]
    if len(s) < 20:
        return None
    return float((s <= s.iloc[-1]).mean() * 100)


def bias_history_for(config_path: Path | str, get_series):
    """Zwraca funkcje (instrument, od, do) -> historia biasu liczona przyczynowo; serie pobierane raz i dzielone."""
    from ..validation.context import bias_history

    components = load_components(config_path)
    shared: dict[str, pd.Series | Exception] = {}

    def cached(series_id: str) -> pd.Series:
        if series_id not in shared:
            try:
                shared[series_id] = get_series(series_id)
            except Exception as exc:  # brak jednej serii nie moze zatrzymac testu
                shared[series_id] = exc
        if isinstance(shared[series_id], Exception):
            raise shared[series_id]
        return shared[series_id]

    def for_instrument(inst, start, end):
        comps = components.get(inst.symbol)
        return bias_history(comps, cached, pd.Timestamp(start), pd.Timestamp(end)) if comps else None

    return for_instrument
