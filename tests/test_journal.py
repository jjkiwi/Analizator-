from datetime import datetime, timezone

import pandas as pd
import pytest

from cfd import journal
from cfd.db import connect
from cfd.models import Costs, Signal


def candles(rows, start="2024-01-01"):
    idx = pd.date_range(start, periods=len(rows), freq="1D", tz="UTC")
    return pd.DataFrame(rows, columns=["open", "high", "low", "close"], index=idx)


def signal(side=1, t="2024-01-01"):
    return Signal("GOLD", "s", datetime.fromisoformat(t).replace(tzinfo=timezone.utc), side, 100.0,
                  100.0 - side * 2, 100.0 + side * 4, "test")


def status(conn):
    r = conn.execute("SELECT status, r_result FROM signals").fetchone()
    return r["status"], r["r_result"]


def test_record_is_idempotent():
    conn = connect(":memory:")
    assert journal.record(conn, signal(), "1d", 1.5, {"a": 1}) is True
    assert journal.record(conn, signal(), "1d") is False
    assert conn.execute("SELECT COUNT(*) FROM signals").fetchone()[0] == 1


def test_resolve_take_profit_uses_next_open_and_skips_unclosed_bar():
    conn = connect(":memory:")
    journal.record(conn, signal(), "1d")
    df = candles([(100, 101, 99, 100), (101, 102, 100, 101), (101, 106, 100.5, 105), (105, 105, 105, 105)])
    # tylko swieca sygnalowa + jedna niedomknieta: nic do rozliczenia
    assert journal.resolve(conn, "GOLD", "1d", df.iloc[:2]) == 0
    assert journal.resolve(conn, "GOLD", "1d", df) == 1
    st, r = status(conn)
    assert st == "tp" and r == pytest.approx(2.0)  # wejscie 101, TP 105, ryzyko 2


def test_resolve_stop_loss_short_with_costs():
    conn = connect(":memory:")
    journal.record(conn, signal(side=-1), "1d")
    df = candles([(100, 101, 99, 100), (100, 103, 99.5, 102), (102, 102, 102, 102)])
    journal.resolve(conn, "GOLD", "1d", df, Costs(spread_pct=0.01))
    st, r = status(conn)
    assert st == "sl" and r == pytest.approx((-2 - 1.0) / 2)


def test_resolve_expires():
    conn = connect(":memory:")
    journal.record(conn, signal(), "1d")
    df = candles([(100, 100.5, 99.5, 100)] * 6)
    journal.resolve(conn, "GOLD", "1d", df, expire_bars=3)
    st, r = status(conn)
    assert st == "expired" and r == pytest.approx(0.0)
    assert journal.stats(conn)[0]["resolved"] == 1
