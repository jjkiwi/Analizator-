import pandas as pd
import pytest

from cfd.backtest import run_backtest, summarize
from cfd.models import Costs
from cfd.strategies import TrendPullback


def frame(rows):
    idx = pd.date_range("2024-01-01", periods=len(rows), freq="1D", tz="UTC")
    return pd.DataFrame(rows, columns=["open", "high", "low", "close"], index=idx)


def sig(df, i, side, sl=2.0, tp=4.0):
    s = pd.DataFrame({"side": 0, "sl_dist": sl, "tp_dist": tp}, index=df.index)
    s.iloc[i, 0] = side
    return s


def test_long_hits_take_profit_enters_next_open():
    df = frame([(100, 101, 99, 100), (100, 101, 99.5, 100.5), (100.5, 105, 100, 104)])
    (t,) = run_backtest(df, sig(df, 0, 1))
    assert t.entry_price == 100 and t.exit_price == 104 and t.exit_reason == "tp"
    assert t.r_multiple == pytest.approx(2.0)


def test_sl_wins_when_both_levels_in_one_bar():
    df = frame([(100, 101, 99, 100), (100, 105, 97, 100)])
    (t,) = run_backtest(df, sig(df, 0, 1))
    assert t.exit_reason == "sl" and t.r_multiple == pytest.approx(-1.0)


def test_gap_through_stop_fills_at_open():
    df = frame([(100, 101, 99, 100), (100, 100.5, 99.5, 100), (95, 96, 94, 95)])
    (t,) = run_backtest(df, sig(df, 0, 1))
    assert t.exit_price == 95 and t.r_multiple == pytest.approx(-2.5)


def test_short_and_costs():
    df = frame([(100, 101, 99, 100), (100, 100.5, 99.5, 100), (100, 100.2, 95, 96)])
    costs = Costs(spread_pct=0.001, swap_short_annual_pct=0.0365)
    (t,) = run_backtest(df, sig(df, 0, -1), costs)
    # brutto +4 (=2R); spread 0.1 + swap za 1 noc 0.01 -> koszt 0.11
    assert t.exit_reason == "tp"
    assert t.cost == pytest.approx(0.11)
    assert t.r_multiple == pytest.approx((4 - 0.11) / 2)


def test_one_position_at_a_time_and_end_close():
    df = frame([(100, 101, 99, 100)] * 5)
    s = pd.DataFrame({"side": 1, "sl_dist": 5.0, "tp_dist": 5.0}, index=df.index)
    trades = run_backtest(df, s)
    assert len(trades) == 1 and trades[0].exit_reason == "end"


def test_strategy_end_to_end_and_costs_hurt(candles):
    signals = TrendPullback().generate(candles)
    assert set(signals["side"].unique()) <= {-1, 0, 1}
    free = summarize(run_backtest(candles, signals))
    paid = summarize(run_backtest(candles, signals, Costs(spread_pct=0.002)))
    assert free["trades"] > 5
    assert paid["total_r"] < free["total_r"]
    assert paid["max_drawdown_pct"] <= 0


def test_strategy_signals_do_not_look_ahead(candles):
    full = TrendPullback().generate(candles)
    part = TrendPullback().generate(candles.iloc[:1000])
    assert (full["side"].iloc[:1000] == part["side"]).all()
