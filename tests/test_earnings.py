import numpy as np
import pandas as pd

from cfd.validation.earnings import evaluate, event_rows, verdict


def _series(n=400, seed=0):
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2020-01-01", periods=n)
    mkt = pd.Series(100 * np.exp(np.cumsum(rng.normal(0, 0.01, n))), index=idx)
    return idx, mkt


def test_event_timing_after_close_and_no_look_ahead():
    idx, mkt = _series()
    px = mkt.copy()
    px.iloc[101:] *= 1.10                      # skok w sesji 101
    t_after = pd.Timestamp(idx[100].date()).tz_localize("America/New_York") + pd.Timedelta(hours=16, minutes=30)
    t_before = pd.Timestamp(idx[101].date()).tz_localize("America/New_York") + pd.Timedelta(hours=7)
    r1 = event_rows([t_after.tz_convert("UTC")], px, mkt)[0]
    r2 = event_rows([t_before.tz_convert("UTC")], px, mkt)[0]
    assert r1["date"] == idx[101] == r2["date"]            # po zamknieciu = nastepna sesja
    assert abs(r1["reaction"] - 0.10) < 0.01 and abs(r1["drift"]) < 1e-9   # nadwyzka nad rynkiem: 0,10 x ruch rynku
    px2 = px.copy(); px2.iloc[103:] *= 2                    # zmiana po wejsciu nie zmienia reakcji
    assert event_rows([t_after.tz_convert("UTC")], px2, mkt)[0]["reaction"] == r1["reaction"]


def test_evaluate_detects_drift_and_rejects_noise():
    rng = np.random.default_rng(1)
    n = 1200
    dates = pd.bdate_range("2012-01-01", periods=n)
    reaction = rng.normal(0, 0.05, n)
    real = pd.DataFrame({"date": dates, "reaction": reaction, "drift": 0.3 * reaction + rng.normal(0.004, 0.05, n)})
    noise = pd.DataFrame({"date": dates, "reaction": reaction, "drift": rng.normal(0, 0.05, n)})
    assert verdict(evaluate(real))[0]
    assert not verdict(evaluate(noise))[0]
