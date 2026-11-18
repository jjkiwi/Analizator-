import numpy as np
import pandas as pd

from cfd.validation.calendar_vol import h9_report, t_stat, turn_of_month, vol_managed


def test_vol_managed_is_causal_and_capped():
    rng = np.random.default_rng(0)
    idx = pd.bdate_range("2000-01-03", periods=3000)
    vol = np.where((np.arange(3000) // 250) % 2 == 0, 0.005, 0.03)
    rets = pd.DataFrame({"A": rng.normal(0.0003, vol)}, index=idx)
    df = vol_managed(rets)
    assert df["w"].max() <= 1.0 + 1e-12
    cut = idx[2000]
    rets2 = rets.copy(); rets2.loc[rets2.index > cut, "A"] *= 5
    df2 = vol_managed(rets2)
    pd.testing.assert_series_equal(df["w"][df.index <= cut], df2["w"][df2.index <= cut])   # przyszlosc nie zmienia ekspozycji
    rep = h9_report(df)
    assert rep["potwierdzajaca"]["managed"]["max_dd"] >= rep["potwierdzajaca"]["base"]["max_dd"] - 0.05


def test_turn_of_month_detects_planted_effect():
    rng = np.random.default_rng(1)
    idx = pd.bdate_range("1990-01-01", "2020-12-31")
    r = pd.Series(rng.normal(0, 0.01, len(idx)), index=idx)
    per = idx.to_period("M")
    pos = pd.Series(range(len(idx)), index=idx).groupby(per).transform(lambda s: s - s.iloc[0])
    last = pd.Series(range(len(idx)), index=idx).groupby(per).transform(lambda s: s.iloc[-1] - s)
    r[(pos < 3) | (last == 0)] += 0.002
    tom = turn_of_month(pd.DataFrame({"A": r}))
    assert tom["excess"].mean() > 0.005 and t_stat(tom["excess"]) > 3
    noise = turn_of_month(pd.DataFrame({"A": pd.Series(rng.normal(0, 0.01, len(idx)), index=idx)}))
    assert abs(t_stat(noise["excess"])) < 3
