"""Prosty, konserwatywny backtest: jedna pozycja naraz, wejscie na otwarciu nastepnej swiecy.

Zalozenia (wszystkie na niekorzysc strategii):
- sygnal z zamkniecia swiecy i, wejscie po cenie otwarcia swiecy i+1,
- jesli w jednej swiecy zasieg obejmuje i SL, i TP, przyjmujemy SL,
- luka przez poziom = realizacja po cenie otwarcia (gorszej niz poziom dla SL),
- spread odejmowany w calosci, swap naliczany za kazda noc kalendarzowa.

Rolowanie (`roll`): na pierwszej swiecy po wygasnieciu kontraktu seria ciagla przeskakuje na nowy kontrakt.
Tej roznicy na CFD nie da sie zarobic ani stracic (broker wyrownuje ja korekta przy rolowaniu), wiec otwarta
pozycja jest przesuwana o luke otwarcia: wejscie, SL i TP razem. Luka nie daje wtedy ani zysku, ani straty.
"""
from __future__ import annotations

import pandas as pd

import numpy as np

from ..models import Costs, Trade


def run_backtest(
    df: pd.DataFrame,
    signals: pd.DataFrame,
    costs: Costs = Costs(),
    max_bars: int | None = None,
    roll: pd.Series | np.ndarray | None = None,
) -> list[Trade]:
    o, h, l, c = (df[k].to_numpy() for k in ("open", "high", "low", "close"))
    side = signals["side"].to_numpy()
    sl_d = signals["sl_dist"].to_numpy()
    tp_d = signals["tp_dist"].to_numpy()
    times = df.index
    n = len(df)
    is_roll = np.zeros(n, dtype=bool) if roll is None else np.asarray(roll, dtype=bool)
    trades: list[Trade] = []
    pos: dict | None = None

    def close(i: int, price: float, reason: str) -> None:
        nonlocal pos
        gross = (price - pos["entry"]) * pos["side"]
        nights = max((times[i].normalize() - times[pos["i"]].normalize()).days, 0)
        swap_rate = costs.swap_long_annual_pct if pos["side"] > 0 else costs.swap_short_annual_pct
        cost = pos["entry"] * (costs.spread_pct + swap_rate * nights / 365)
        trades.append(
            Trade(
                side=pos["side"],
                entry_time=times[pos["i"]].to_pydatetime(),
                exit_time=times[i].to_pydatetime(),
                entry_price=float(pos["entry"]),
                exit_price=float(price),
                exit_reason=reason,
                bars_held=i - pos["i"] + 1,
                cost=float(cost),
                cost_r=float(cost / pos["risk"]),
                r_multiple=float((gross - cost) / pos["risk"]),
            )
        )
        pos = None

    for i in range(n):
        if pos is not None and i > pos["i"] and is_roll[i] and not is_roll[i - 1]:
            shift = o[i] - c[i - 1]  # luka rolowania: przesuwamy cala pozycje, wynik bez zmian
            pos["entry"] += shift
            pos["sl"] += shift
            pos["tp"] += shift
        if pos is not None:
            s, sl, tp = pos["side"], pos["sl"], pos["tp"]
            if s > 0:
                if l[i] <= sl:
                    close(i, min(o[i], sl), "sl")
                elif h[i] >= tp:
                    close(i, max(o[i], tp), "tp")
            else:
                if h[i] >= sl:
                    close(i, max(o[i], sl), "sl")
                elif l[i] <= tp:
                    close(i, min(o[i], tp), "tp")
            if pos is not None and max_bars and i - pos["i"] + 1 >= max_bars:
                close(i, c[i], "timeout")

        if pos is None and i + 1 < n and side[i] != 0 and sl_d[i] > 0 and tp_d[i] > 0:
            entry = o[i + 1]
            s = int(side[i])
            pos = {
                "side": s,
                "i": i + 1,
                "entry": entry,
                "sl": entry - s * sl_d[i],
                "tp": entry + s * tp_d[i],
                "risk": sl_d[i],
            }

    if pos is not None:
        close(n - 1, c[n - 1], "end")
    return trades
