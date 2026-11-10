import numpy as np
import pandas as pd

from cfd.features import atr, ema, rsi


def test_ema_of_constant_is_constant():
    s = pd.Series([5.0] * 50)
    assert np.allclose(ema(s, 10).dropna(), 5.0)


def test_rsi_bounds_and_extremes(candles):
    r = rsi(candles["close"]).dropna()
    assert r.between(0, 100).all()
    rising = pd.Series(np.arange(1.0, 60.0))
    assert rsi(rising).iloc[-1] == 100.0


def test_atr_positive(candles):
    assert (atr(candles).dropna() > 0).all()


def test_indicators_do_not_look_ahead(candles):
    full = rsi(candles["close"])
    part = rsi(candles["close"].iloc[:800])
    assert np.allclose(full.iloc[:800].dropna(), part.dropna())
