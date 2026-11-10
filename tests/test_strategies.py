import numpy as np
import pandas as pd
import pytest

from cfd.features import adx, bollinger, donchian, macd, regime
from cfd.strategies import PARAM_GRIDS, REGISTRY
from cfd.validation import verdict, walk_forward

from conftest import make_candles


def test_adx_bounds_and_trend_detection():
    trending = make_candles(600, seed=2, drift=0.004, vol=0.004)
    choppy = make_candles(600, seed=2, drift=0.0, vol=0.01)
    assert adx(trending).dropna().between(0, 100).all()
    assert adx(trending).iloc[-100:].mean() > adx(choppy).iloc[-100:].mean()
    assert regime(trending).iloc[-1] == "trend_up"


def test_bollinger_and_macd_shapes(candles):
    bb = bollinger(candles["close"]).dropna()
    assert (bb["upper"] >= bb["mid"]).all() and (bb["mid"] >= bb["lower"]).all()
    m = macd(candles["close"]).dropna()
    assert np.allclose(m["hist"], m["macd"] - m["signal"])


def test_donchian_excludes_current_bar(candles):
    ch = donchian(candles, 20)
    i = 100
    assert ch["upper"].iloc[i] == candles["high"].iloc[i - 20 : i].max()


@pytest.mark.parametrize("name", sorted(REGISTRY))
def test_every_strategy_is_valid_and_causal(name, candles):
    strat = REGISTRY[name]()
    full = strat.generate(candles)
    assert {"side", "sl_dist", "tp_dist", "rationale"} <= set(full.columns)
    assert set(full["side"].unique()) <= {-1, 0, 1}
    active = full[full["side"] != 0]
    assert (active["sl_dist"] > 0).all() and (active["tp_dist"] > 0).all()
    assert (active["rationale"] != "").all()
    part = strat.generate(candles.iloc[:900])
    assert (full["side"].iloc[:900].to_numpy() == part["side"].to_numpy()).all()
    assert set(PARAM_GRIDS[name]) <= set(vars(strat))


def test_walk_forward_trades_only_in_test_windows():
    df = make_candles(2500, seed=5, drift=0.0006)
    res = walk_forward(df, REGISTRY["trend_pullback"], PARAM_GRIDS["trend_pullback"], train_bars=750, test_bars=250, min_train_trades=3)
    assert len(res.folds) == (2500 - 750) // 250
    first_test = res.folds[0]["test_start"]
    assert all(pd.Timestamp(t.entry_time) >= first_test for t in res.trades)
    assert sum(f["test_trades"] for f in res.folds) == len(res.trades)


def test_verdict_thresholds():
    folds = [{"test_trades": 5, "test_total_r": 1.0}] * 6 + [{"test_trades": 5, "test_total_r": -1.0}] * 2
    good = {"trades": 40, "expectancy_r": 0.3, "profit_factor": 1.6}
    assert verdict(good, folds)[0] == "pass"
    assert verdict({**good, "trades": 10}, folds)[0] == "fail"
    assert verdict({**good, "expectancy_r": -0.1}, folds)[0] == "fail"
    assert verdict({**good, "profit_factor": 1.1}, folds)[0] == "weak"
