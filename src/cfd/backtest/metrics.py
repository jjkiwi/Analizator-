from __future__ import annotations

import numpy as np

from ..models import Trade


def summarize(trades: list[Trade], risk_per_trade: float = 0.01) -> dict:
    """Statystyki w wielokrotnosciach ryzyka (R). Kapital liczony przy stalym ryzyku na transakcje."""
    if not trades:
        return {"trades": 0}
    r = np.array([t.r_multiple for t in trades])
    wins, losses = r[r > 0], r[r <= 0]
    equity = np.cumprod(1 + risk_per_trade * r)
    peak = np.maximum.accumulate(np.concatenate([[1.0], equity]))[1:]
    return {
        "trades": len(r),
        "win_rate": float(len(wins) / len(r)),
        "expectancy_r": float(r.mean()),
        "profit_factor": float(wins.sum() / -losses.sum()) if losses.sum() < 0 else float("inf"),
        "total_r": float(r.sum()),
        "costs_total_r": float(sum(t.cost_r for t in trades)),
        "max_drawdown_pct": float(((equity - peak) / peak).min() * 100),
        "return_pct": float((equity[-1] - 1) * 100),
        "avg_bars_held": float(np.mean([t.bars_held for t in trades])),
    }
