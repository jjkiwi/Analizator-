"""Dziennik sygnalow = forward test. Kazdy sygnal jest zapisywany i pozniej rozliczany na nowych swiecach."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime

import pandas as pd

from .models import Costs, Signal


def record(conn: sqlite3.Connection, sig: Signal, interval: str, score: float | None = None, context: dict | None = None) -> bool:
    """Zapisuje sygnal. Zwraca True, jesli jest nowy (czyli warto wyslac alert)."""
    cur = conn.execute(
        """INSERT OR IGNORE INTO signals
           (symbol, strategy, interval, time, side, ref_price, stop_loss, take_profit, rationale, score, context)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (sig.symbol, sig.strategy, interval, sig.time.isoformat(), sig.side, sig.ref_price,
         sig.stop_loss, sig.take_profit, sig.rationale, score, json.dumps(context or {}, ensure_ascii=False)),
    )
    conn.commit()
    return cur.rowcount == 1


def resolve(conn: sqlite3.Connection, symbol: str, interval: str, df: pd.DataFrame,
            costs: Costs = Costs(), expire_bars: int = 40) -> int:
    """Rozlicza otwarte sygnaly dla instrumentu na swiecach PO swiecy sygnalowej.

    Reguly jak w backtescie: wejscie na otwarciu nastepnej swiecy, SL ma pierwszenstwo,
    brak rozstrzygniecia po `expire_bars` = 'expired' z wynikiem po cenie zamkniecia.
    Ostatnia swieca w df jest traktowana jako niedomknieta i pomijana.
    """
    closed = df.iloc[:-1]
    rows = conn.execute(
        "SELECT * FROM signals WHERE symbol=? AND interval=? AND status='open'", (symbol, interval)
    ).fetchall()
    done = 0
    for row in rows:
        after = closed[closed.index > pd.Timestamp(row["time"])]
        if after.empty:
            continue
        side = row["side"]
        entry = float(after["open"].iloc[0])
        sl_dist = abs(row["ref_price"] - row["stop_loss"])
        tp_dist = abs(row["take_profit"] - row["ref_price"])
        sl, tp = entry - side * sl_dist, entry + side * tp_dist
        status = exit_price = exit_time = None
        for i, (ts, bar) in enumerate(after.iterrows()):
            hit_sl = bar["low"] <= sl if side > 0 else bar["high"] >= sl
            hit_tp = bar["high"] >= tp if side > 0 else bar["low"] <= tp
            if hit_sl:
                status = "sl"
                exit_price = min(bar["open"], sl) if side > 0 else max(bar["open"], sl)
            elif hit_tp:
                status = "tp"
                exit_price = max(bar["open"], tp) if side > 0 else min(bar["open"], tp)
            elif i + 1 >= expire_bars:
                status, exit_price = "expired", bar["close"]
            if status:
                exit_time = ts
                break
        if not status:
            continue
        nights = max((exit_time.normalize() - after.index[0].normalize()).days, 0)
        swap = costs.swap_long_annual_pct if side > 0 else costs.swap_short_annual_pct
        cost = entry * (costs.spread_pct + swap * nights / 365)
        r = ((exit_price - entry) * side - cost) / sl_dist if sl_dist > 0 else 0.0
        conn.execute(
            "UPDATE signals SET status=?, resolved_time=?, r_result=? WHERE id=?",
            (status, exit_time.isoformat(), float(r), row["id"]),
        )
        done += 1
    conn.commit()
    return done


def stats(conn: sqlite3.Connection) -> list[dict]:
    """Skutecznosc na zywo per strategia: to te liczby rozstrzygaja, czy backtest mowil prawde."""
    rows = conn.execute(
        """SELECT strategy, interval,
                  COUNT(*) AS total,
                  SUM(status='open') AS open,
                  SUM(status!='open') AS resolved,
                  SUM(r_result > 0) AS wins,
                  AVG(r_result) AS expectancy_r,
                  SUM(r_result) AS total_r
           FROM signals GROUP BY strategy, interval ORDER BY strategy, interval"""
    ).fetchall()
    return [dict(r) for r in rows]


def recent(conn: sqlite3.Connection, limit: int = 30) -> list[dict]:
    rows = conn.execute("SELECT * FROM signals ORDER BY time DESC, id DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]


def last_signal_time(conn: sqlite3.Connection) -> datetime | None:
    row = conn.execute("SELECT MAX(time) AS t FROM signals").fetchone()
    return datetime.fromisoformat(row["t"]) if row and row["t"] else None
