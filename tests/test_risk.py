import numpy as np
import pandas as pd

from cfd.validation.risk import sma_rule, vix_episodes, vix_signal


def _idx(n):
    return pd.date_range("2000-01-03", periods=n, freq="B")


def test_vix_signal_causal():
    rng = np.random.default_rng(1)
    v = pd.Series(20 + rng.normal(0, 1, 400), index=_idx(400))
    a = vix_signal(v)
    v2 = v.copy(); v2.iloc[350:] = 80
    b = vix_signal(v2)
    assert (a.iloc[:350] == b.iloc[:350]).all()
    assert b.iloc[350]


def test_vix_episodes_no_overlap():
    n = 400
    v = pd.Series(20.0, index=_idx(n)); v.iloc[300:320] = 50
    spx = pd.Series(np.linspace(100, 200, n), index=_idx(n))
    ep = vix_episodes(v, spx, hold=20)
    assert len(ep) == 1
    assert ep["entry"].iloc[0] == v.index[301]


def test_sma_rule_causal():
    rng = np.random.default_rng(2)
    c = pd.DataFrame({"A": 100 * np.exp(np.cumsum(rng.normal(0, .01, 500))),
                      "B": 100 * np.exp(np.cumsum(rng.normal(0, .01, 500)))}, index=_idx(500))
    a = sma_rule(c)
    c2 = c.copy(); c2.iloc[450:] *= 3
    b = sma_rule(c2)
    common = a.index[a.index < c.index[450]]
    pd.testing.assert_frame_equal(a.loc[common], b.loc[common], check_freq=False)
