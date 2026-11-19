import numpy as np
import pandas as pd

from cfd.model.vol import FEATURES, HAR, build, instrument_vol_frame, qlike


def _df(n=400, seed=0, shock_at=None):
    rng = np.random.default_rng(seed)
    sig = np.where(np.arange(n) % 200 < 100, 0.01, 0.03)
    r = rng.normal(0, sig)
    c = 100 * np.exp(np.cumsum(r))
    idx = pd.date_range("2010-01-01", periods=n, freq="B")
    df = pd.DataFrame({"open": c, "high": c * (1 + sig), "low": c * (1 - sig), "close": c}, index=idx)
    if shock_at is not None:
        df.iloc[shock_at:, :] *= 1.5
    return df


def test_features_causal():
    a = instrument_vol_frame(_df())
    b = instrument_vol_frame(_df(shock_at=300))
    cols = FEATURES + ["naive", "ewma"]
    pd.testing.assert_frame_equal(a.iloc[:300][cols], b.iloc[:300][cols])


def test_target_is_future():
    f = instrument_vol_frame(_df())
    c = np.log(_df()["close"])
    r2 = c.diff() ** 2
    assert abs(f["rv"].iloc[100] - r2.iloc[101:106].sum()) < 1e-12


def test_har_beats_constant_on_clustered_vol():
    ds = build({f"S{i}": _df(seed=i) for i in range(4)})
    m = HAR().fit(ds)
    f = m.predict(ds)
    const = np.full(len(ds), ds["rv"].mean())
    assert qlike(ds["rv"].to_numpy(), f).mean() < qlike(ds["rv"].to_numpy(), const).mean()


def test_predict_ranges_and_render():
    from cfd.command import _ranges
    from cfd.model.vol import predict_ranges, train_doc

    frames = {f"S{i}": _df(n=6200, seed=i) for i in range(3)}
    frames = {k: v.set_index(pd.date_range("2002-01-01", periods=len(v), freq="B")) for k, v in frames.items()}
    doc = train_doc(frames)
    items = predict_ranges(frames, doc)
    assert len(items) == 3
    r = items[0]
    assert r["lo"] < r["price"] < r["hi"] and r["lo_pct"] < 0 < r["hi_pct"]
    html = _ranges({"ranges": {"passed": True, "horizon": 5, "items": items}})
    assert "Zakres 80%" in html and "S0" in html


def test_range_log_roundtrip(tmp_path):
    from cfd.model.vol import append_range_log, score_range_log

    items = [{"date": "2026-01-05", "symbol": "X", "horizon": 2, "price": 100.0, "lo": 95.0, "hi": 105.0}]
    p = tmp_path / "z.csv"
    assert append_range_log(items, p) == 1 and append_range_log(items, p) == 0
    c = pd.Series([100.0, 101.0, 110.0, 99.0], index=pd.to_datetime(["2026-01-05", "2026-01-06", "2026-01-07", "2026-01-08"]))
    assert score_range_log(pd.read_csv(p), {"X": c}) == {"n": 1, "coverage": 0.0}
