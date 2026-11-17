"""Model H5: przyczynowosc cech, oczyszczanie i embargo, test przecieku, wykrywanie sygnalu, format prognoz."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from cfd.model import evaluate as mev
from cfd.model import predict as mpr
from cfd.model.features import FEATURES, NUMERIC, add_targets, build_dataset, instrument_features


def _ohlc(n: int, seed: int, start="2015-01-01") -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range(start, periods=n, tz="UTC")
    c = 100 * np.exp(np.cumsum(rng.normal(0.0003, 0.012, n)))
    o = c * np.exp(rng.normal(0, 0.003, n))
    hi = np.maximum(o, c) * (1 + rng.uniform(0, 0.01, n))
    lo = np.minimum(o, c) * (1 - rng.uniform(0, 0.01, n))
    return pd.DataFrame({"open": o, "high": hi, "low": lo, "close": c, "volume": 1.0}, index=idx)


def test_features_causal():
    """Cechy w dniu t nie zmieniaja sie, gdy usuniemy dane z przyszlosci (instrument i rynek)."""
    df, mk = _ohlc(700, 1), _ohlc(700, 2)
    full = instrument_features(df, "stocks", mk["close"])
    for k in (300, 450, 699):
        part = instrument_features(df.iloc[:k], "stocks", mk["close"].iloc[:k])
        a, b = full.loc[part.index, NUMERIC], part[NUMERIC]
        pd.testing.assert_frame_equal(a, b, check_exact=False, rtol=1e-9)
    assert full[NUMERIC].iloc[300:].notna().all().all()


def test_targets_look_ahead():
    """Cel to kierunek z t+1..t+h; ostatnie h wierszy bez celu; end_h = data swiecy t+h."""
    df = _ohlc(300, 3)
    f = add_targets(instrument_features(df, "indices"), (5,))
    c = df["close"].to_numpy()
    assert f["y_5"].iloc[-5:].isna().all()
    assert f["y_5"].iloc[10] == float(c[15] > c[10])
    assert f["end_5"].iloc[10] == df.index[15]


def _synthetic(n_days=1500, n_sym=8, signal=0.0, seed=0, h=5) -> pd.DataFrame:
    """Zbior w ukladzie build_dataset z losowymi cechami; cel zalezy od ret_5 z sila `signal` (0 = brak sygnalu)."""
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2010-01-01", periods=n_days, tz="UTC")
    parts = []
    for s in range(n_sym):
        f = pd.DataFrame(rng.normal(size=(n_days, len(NUMERIC))), columns=NUMERIC)
        for cat in ("indices", "stocks", "metals", "crypto"):
            f[f"cat_{cat}"] = 1.0 if cat == ("stocks" if s % 2 else "indices") else 0.0
        z = signal * f["ret_5"].to_numpy() + rng.normal(size=n_days)
        f["date"] = dates
        f["symbol"] = f"S{s}"
        f["category"] = "stocks" if s % 2 else "indices"
        f["close"] = 100.0
        for hh in (5, 20):
            f[f"y_{hh}"] = (z > 0).astype(float)
            f[f"end_{hh}"] = pd.Series(dates).shift(-hh)
            f.loc[f.index[-hh:], f"y_{hh}"] = np.nan
        parts.append(f)
    return pd.concat(parts, ignore_index=True).sort_values(["date", "symbol"]).reset_index(drop=True)


@pytest.mark.parametrize("h", [5, 20])
def test_purging_embargo(h):
    """Zaden wiersz treningowy nie ma okna celu nachodzacego na okres testowy (z zapasem embargo)."""
    ds = _synthetic(n_days=1200, n_sym=3)
    sp = mev.chronological_split(ds, h)
    emb = pd.Timedelta(days=mev.embargo_days(h))
    pairs = [(sp["train"], sp["val"]), (sp["pretest"], sp["test"]), (sp["val"], sp["test"])]
    pairs += mev.walk_forward_splits(ds, h, sp["pretest"])
    for tr, te in pairs:
        assert tr.any() and te.any()
        assert ds.loc[tr, f"end_{h}"].max() + emb <= ds.loc[te, "date"].min()
        assert not (tr & te).any()
    assert ds.loc[sp["pretest"], f"end_{h}"].max() < sp["test_start"]


def test_leak_no_skill_on_random_target():
    """Gdy cel jest losowy, model nie moze miec istotnego skilla ani przejsc kryterium H5."""
    ds = _synthetic(signal=0.0, seed=4)
    r = mev.evaluate_horizon(ds, 5)
    assert not r["passed"]
    assert r["skill"] == "brak"
    assert r["test"]["bss"] < 0.01
    assert abs(r["test"]["auc"] - 0.5) < 0.03


def test_detects_real_signal():
    """Wbudowana zaleznosc celu od cechy: model ja wykrywa, przechodzi kryterium, a test przecieku daje ~0."""
    ds = _synthetic(signal=0.5, seed=5)
    r = mev.evaluate_horizon(ds, 5)
    assert r["test"]["bss"] > 0.02
    assert r["bootstrap"]["p_brier"] < 0.01
    assert r["passed"] and r["skill"] == "jest"
    assert r["leak_test"]["ok"]
    j = FEATURES.index("ret_5")
    top = max(r["coef_stability"], key=lambda c: abs(c["mean"]))
    assert top["feature"] == "ret_5" and top["mean"] > 0 and top["same_sign_share"] == 1.0
    assert r["coef_test_model"]["ret_5"] > 0 and j >= 0


def test_metrics_basic():
    y = np.array([0, 1, 1, 0, 1])
    assert mev.auc([0.1, 0.9, 0.8, 0.2, 0.7], y) == 1.0
    assert mev.brier([0.5] * 5, y) == 0.25
    assert mev.block_bootstrap_p(np.full(200, 0.01) + np.random.default_rng(0).normal(0, 0.001, 200), 20) < 0.01


def test_predictions_format_and_log(tmp_path):
    frames = {"US500": _ohlc(400, 7), "AAA": _ohlc(400, 8), "BBB": _ohlc(400, 9)}
    cats = {"US500": "indices", "AAA": "stocks", "BBB": "metals"}
    ds = build_dataset(frames, cats)
    res = mev.run(ds, horizons=(5,))
    doc = {"generated": res["generated"], "horizons": res["horizons"]}
    items = mpr.predict_latest(ds, doc, horizons=(5,))
    assert len(items) == 3
    for it in items:
        assert set(it) >= {"symbol", "horizon", "p_up", "base_rate", "skill"}
        assert 0 < it["p_up"] < 1 and it["horizon"] == 5
        assert it["skill"] in ("brak", "słaby", "jest") and it["skill"] == res["horizons"]["5"]["skill"]
    out = mpr.write_predictions(items, doc, tmp_path / "prognozy.json")
    assert out.exists()
    log = tmp_path / "log.csv"
    assert mpr.append_log(items, log) == 3
    assert mpr.append_log(items, log) == 0          # jeden wpis na dzien/symbol/h
    # ocena w przod: wpis z ceny sprzed 5 sesji zostaje rozliczony
    df = pd.read_csv(log)
    df["date"] = str(frames["AAA"].index[-10].date())
    df["price"] = [float(frames[s]["close"].iloc[-10]) for s in df["symbol"]]
    sc = mpr.score_log(df, {s: f["close"] for s, f in frames.items()})
    assert sc["n_scored"] == 3 and sc["horizons"]["5"]["n"] == 3
