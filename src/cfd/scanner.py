from __future__ import annotations

from datetime import datetime

import pandas as pd

from .models import Instrument, Signal


def due_intervals(now: datetime, configured: list[str]) -> list[str]:
    """Interwaly, na ktorych od ostatniego polgodzinnego przebiegu mogla zamknac sie swieca.

    30m: zawsze; 1h: w pierwszej polowie godziny; 4h i 1d: w pierwszej polowie co czwartej godziny UTC.
    Dzienna swieca jest sprawdzana 6 razy na dobe, bo rynki zamykaja sie o roznych porach
    (dziennik i tak nie przyjmie dwa razy tego samego sygnalu).
    """
    first_half = now.minute < 30
    due = {"30m"}
    if first_half:
        due.add("1h")
        if now.hour % 4 == 0:
            due |= {"4h", "1d"}
    return [i for i in configured if i in due]


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
