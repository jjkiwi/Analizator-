import numpy as np
import pandas as pd
import pytest


def make_candles(n=1500, seed=1, drift=0.0003, vol=0.01, freq="1D"):
    rng = np.random.default_rng(seed)
    close = 100 * np.exp(np.cumsum(rng.normal(drift, vol, n)))
    open_ = np.concatenate([[100.0], close[:-1]])
    spread = np.abs(rng.normal(0, vol / 2, n)) * close
    df = pd.DataFrame(
        {
            "open": open_,
            "high": np.maximum(open_, close) + spread,
            "low": np.minimum(open_, close) - spread,
            "close": close,
            "volume": 1000.0,
        },
        index=pd.date_range("2018-01-01", periods=n, freq=freq, tz="UTC", name="time"),
    )
    return df


@pytest.fixture
def candles():
    return make_candles()
