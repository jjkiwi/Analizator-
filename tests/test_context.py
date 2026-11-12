import numpy as np
import pandas as pd

from cfd.validation.context import FEATURES, bias_history, evaluate, label_trades

from conftest import make_candles


def _trades(df, n=40, seed=1):
    rng = np.random.default_rng(seed)
    pos = np.sort(rng.choice(np.arange(300, len(df) - 5), n, replace=False))
    return pd.DataFrame({"entry_time": df.index[pos], "side": rng.choice([-1, 1], n), "r": rng.normal(0, 1, n)})


def test_labels_are_causal_no_look_ahead():
    """Etykieta transakcji nie moze sie zmienic, gdy zmienimy dane od swiecy wejscia wlacznie."""
    df = make_candles(900, seed=3)
    vix = pd.Series(np.linspace(12, 30, len(df)), index=df.index)
    bias = pd.Series(np.sin(np.arange(len(df)) / 30) * 2, index=df.index)
    tr = _trades(df)
    base = label_trades(tr, df, df, "1d", vix, bias)
    cut = tr["entry_time"].iloc[20]
    df2 = df.copy()
    df2.loc[df2.index >= cut, ["open", "high", "low", "close"]] *= 3.0
    vix2, bias2 = vix.copy(), bias.copy()
    vix2[vix2.index >= cut.normalize()] = 99.0
    bias2[bias2.index >= cut] = -bias2[bias2.index >= cut]
    changed = label_trades(tr, df2, df2, "1d", vix2, bias2)
    early = tr["entry_time"] <= cut
    for feat in FEATURES:
        assert (base.loc[early, feat] == changed.loc[early, feat]).all(), feat


def test_bias_history_uses_only_published_data():
    idx = pd.date_range("2024-01-01", periods=400, freq="D")
    s = pd.Series(np.arange(400, dtype=float), index=idx)
    seen = []

    def get(_id):
        return s

    comps = [{"series": "X", "lookback": 20, "sign": 1}]
    import cfd.validation.context as ctx

    orig = ctx.compute_bias
    ctx.compute_bias = lambda c, g, now=None: (seen.append((now, g("X").index.max())) or (0.0, []))
    try:
        bias_history(comps, get, pd.Timestamp("2024-06-01", tz="UTC"), pd.Timestamp("2024-07-01", tz="UTC"))
    finally:
        ctx.compute_bias = orig
    assert seen and all(last <= pd.Timestamp(now) for now, last in seen)
    assert all((pd.Timestamp(now) - last).days <= 1 for now, last in seen)  # obciecie dokladnie na dacie publikacji


def test_evaluate_confirms_real_effect_and_rejects_noise():
    rng = np.random.default_rng(0)
    n = 6000
    t = pd.date_range("2020-01-01", periods=n, freq="h", tz="UTC")
    good = rng.random(n) < 0.5
    df = pd.DataFrame({
        "symbol": "X", "category": "indices", "interval": "1h", "strategy": "s", "entry_time": t,
        "side": 1, "r": rng.normal(0, 1, n) + np.where(good, 0.25, -0.25),
        "regime": np.where(good, "z_trendem", "pod_trend"), "d1_trend": rng.choice(["zgodny", "przeciwny"], n),
        "vol": "srednia", "session": "usa", "vix": "niski", "bias": "brak",
    })
    cells, baseline = evaluate(df)
    by = {(c.scope, c.feature, c.value): c for c in cells}
    assert by[("wszystkie", "regime", "z_trendem")].confirmed
    assert not by[("wszystkie", "regime", "pod_trend")].candidate
    assert not by[("wszystkie", "d1_trend", "zgodny")].confirmed  # cecha losowa
    assert abs(baseline[("1h", "s")]["discovery"][1]) < 0.1
