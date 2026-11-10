from __future__ import annotations

from pathlib import Path

import yaml

from .models import Costs, Instrument

DEFAULT_PATH = Path("config/instruments.yaml")
CATEGORIES = {"indices", "commodities", "metals", "crypto", "stocks"}


def load_instruments(path: Path | str = DEFAULT_PATH) -> dict[str, Instrument]:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    defaults = raw.get("cost_defaults", {})
    out: dict[str, Instrument] = {}
    for row in raw["instruments"]:
        cat = row["category"]
        if cat not in CATEGORIES:
            raise ValueError(f"{row['symbol']}: nieznana kategoria '{cat}'")
        if row["symbol"] in out:
            raise ValueError(f"Zduplikowany symbol: {row['symbol']}")
        cost_cfg = {**defaults.get(cat, {}), **(row.get("costs") or {})}
        out[row["symbol"]] = Instrument(
            symbol=row["symbol"],
            name=row["name"],
            category=cat,
            sources=dict(row.get("sources") or {}),
            costs=Costs(**cost_cfg),
        )
    return out
