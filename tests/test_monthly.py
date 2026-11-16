import numpy as np
import pandas as pd

from cfd.validation import monthly


def _prices(n=60, seed=0, cols=8):
    rng = np.random.default_rng(seed)
    idx = pd.period_range("2015-01", periods=n, freq="M")
    return pd.DataFrame(100 * np.exp(np.cumsum(rng.normal(0.005, 0.05, (n, cols)), axis=0)), index=idx, columns=[f"I{i}" for i in range(cols)])


def test_monthly_closes_drops_unfinished_month():
    idx = pd.date_range("2026-09-01", "2026-11-16", freq="B", tz="UTC")
    m = monthly.monthly_closes({"X": pd.Series(np.arange(len(idx), dtype=float), index=idx)}, now=pd.Timestamp("2026-11-16", tz="UTC"))
    assert [str(p) for p in m.index] == ["2026-09", "2026-10"]


def test_no_look_ahead_in_monthly_results():
    """Wynik przypisany do miesiaca m nie moze zalezec od cen pozniejszych niz koniec miesiaca m."""
    p = _prices()
    spread = pd.Series(0.001, index=p.columns)
    base = monthly.run(p, spread)
    cut = p.index[40]
    p2 = p.copy()
    p2.loc[p2.index > cut] *= np.linspace(2, 5, (p2.index > cut).sum())[:, None]
    changed = monthly.run(p2, spread)
    for name in ("trend", "kup_i_trzymaj", "sila_roznica"):
        a, b = base[name][base[name].index <= cut], changed[name][changed[name].index <= cut]
        pd.testing.assert_series_equal(a, b)


def test_trend_signal_rule_and_costs():
    idx = pd.period_range("2020-01", periods=16, freq="M")
    up = pd.Series(np.linspace(100, 200, 16), index=idx)
    down = pd.Series(np.linspace(200, 100, 16), index=idx)
    sig = monthly.trend_signal(pd.DataFrame({"UP": up, "DOWN": down}))
    assert sig["UP"].iloc[:12].isna().all() and bool(sig["UP"].iloc[12]) and not bool(sig["DOWN"].iloc[12])
    free = monthly.run(pd.DataFrame({"UP": up, "DOWN": down}), pd.Series({"UP": 0.0, "DOWN": 0.0}))
    paid = monthly.run(pd.DataFrame({"UP": up, "DOWN": down}), pd.Series({"UP": 0.01, "DOWN": 0.01}))
    t0 = free["trend"].dropna()
    assert (t0 > 0).all()                                                   # trzyma tylko UP (waga 1/2), DOWN w gotowce
    assert np.isclose(free["trend"].dropna().iloc[0] - paid["trend"].dropna().iloc[0], 0.5 * 0.01)   # koszt wejscia raz
    assert np.isclose(free["trend"].dropna().iloc[1], paid["trend"].dropna().iloc[1])                 # potem bez obrotu
    assert (free["kup_i_trzymaj"].dropna() < free["trend"].dropna()).all()


def test_current_state_and_screen_section():
    from cfd.now import _monthly_section

    idx = pd.period_range("2025-01", periods=16, freq="M")
    prices = pd.DataFrame({"UP": np.linspace(100, 200, 16), "DOWN": np.linspace(200, 100, 16), "NEW": [np.nan] * 10 + [1, 2, 3, 4, 5, 6]}, index=idx)
    state = monthly.current_state(prices)
    by = {r["symbol"]: r for r in state["rows"]}
    assert state["month"] == "2026-04" and by["UP"]["in_trend"] and not by["DOWN"]["in_trend"] and "NEW" not in by
    assert by["UP"]["returns"][12] > 0 > by["DOWN"]["returns"][12]
    for r in state["rows"]:
        r.update(name=r["symbol"], category="indices")
    html = _monthly_section(state)
    assert "nie rekomendacja" in html and "w trendzie 1 z 2" in html and _monthly_section({"month": None, "rows": []}) == ""
