from __future__ import annotations

import pandas as pd

from .models import Instrument, Signal


def latest_signal(inst: Instrument, strategy, df: pd.DataFrame) -> Signal | None:
    """Sygnal z ostatniej ZAMKNIETEJ swiecy (ostatni wiersz df moze byc niedomkniety)."""
    if len(df) < 3:
        return None
    closed = df.iloc[:-1]
    from .data.quality import roll_mask

    if roll_mask(inst, closed)[-1]:
        return None  # swieca rolowania kontraktu: skok ceny jest sztuczny
    row = strategy.generate(closed).iloc[-1]
    if row["side"] == 0 or not (row["sl_dist"] > 0 and row["tp_dist"] > 0):
        return None
    price = float(closed["close"].iloc[-1])
    side = int(row["side"])
    return Signal(
        symbol=inst.symbol,
        strategy=strategy.name,
        time=closed.index[-1].to_pydatetime(),
        side=side,
        ref_price=price,
        stop_loss=price - side * float(row["sl_dist"]),
        take_profit=price + side * float(row["tp_dist"]),
        rationale=row["rationale"],
    )
