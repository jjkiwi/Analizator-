from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
import pytest

from cfd.db import connect
from cfd.fundamentals import component_score, compute_bias, read_bias, save_bias
from cfd.fundamentals.bias import positioning_percentile
from cfd.fusion import confluence
from cfd.macro import FairEconomyCalendar, MacroEvent, MacroRules, parse_value, surprise_effects, upcoming, upsert_events
from cfd.macro.calendar import set_actual

RULES = MacroRules([
    {"name": "cpi", "country": "USD", "match": ["cpi"], "effects": {"US500": -1, "GOLD": -1, "USDIDX": 1}},
    {"name": "oil", "country": "USD", "match": ["crude oil inventories"], "effects": {"OIL": -1}},
])
NOW = datetime(2026, 11, 10, 12, tzinfo=timezone.utc)


@pytest.mark.parametrize("text,expected", [("0.3%", 0.3), ("215K", 215000), ("-1.25M", -1.25e6), ("<0.1%", 0.1), ("", None), (None, None), ("n/a", None), (2, 2.0)])
def test_parse_value(text, expected):
    assert parse_value(text) == expected


def test_surprise_effects():
    hot = MacroEvent(NOW, "USD", "Core CPI m/m", 3, actual=0.4, forecast=0.3)
    assert surprise_effects(hot, RULES) == {"US500": -1, "GOLD": -1, "USDIDX": 1}
    cool = MacroEvent(NOW, "USD", "CPI y/y", 3, actual=2.9, forecast=3.1)
    assert surprise_effects(cool, RULES) == {"US500": 1, "GOLD": 1, "USDIDX": -1}
    assert surprise_effects(MacroEvent(NOW, "USD", "CPI y/y", 3, actual=3.1, forecast=3.1), RULES) == {}
    assert surprise_effects(MacroEvent(NOW, "USD", "CPI y/y", 3, forecast=3.1), RULES) == {}
    assert surprise_effects(MacroEvent(NOW, "GBP", "CPI y/y", 3, actual=4, forecast=3), RULES) == {}


def test_calendar_store_and_manual_actual():
    conn = connect(":memory:")
    ev = MacroEvent(NOW + timedelta(minutes=20), "USD", "Crude Oil Inventories", 3, forecast=1.2e6, previous=-0.5e6)
    upsert_events(conn, [ev, MacroEvent(NOW + timedelta(days=3), "USD", "CPI m/m", 3, forecast=0.3)])
    assert [e.name for e in upcoming(conn, timedelta(minutes=30), 3, NOW)] == ["Crude Oil Inventories"]
    upsert_events(conn, [ev])  # ponowne pobranie nie dubluje i nie kasuje danych
    assert conn.execute("SELECT COUNT(*) FROM macro_events").fetchone()[0] == 2
    done = set_actual(conn, "crude oil", 3.0e6, NOW)
    assert done.forecast == 1.2e6 and surprise_effects(done, RULES) == {"OIL": -1}


def test_faireconomy_parse():
    rows = [
        {"title": "CPI m/m", "country": "usd", "date": "2026-11-12T08:30:00-05:00", "impact": "High", "forecast": "0.3%", "previous": "0.2%"},
        {"title": "Bank Holiday", "country": "JPY", "date": "2026-11-12T00:00:00-05:00", "impact": "Holiday"},
        {"title": "Broken", "country": "EUR", "date": "nie-data", "impact": "Low"},
    ]
    (ev,) = FairEconomyCalendar.parse(rows)
    assert ev.time == datetime(2026, 11, 12, 13, 30, tzinfo=timezone.utc)
    assert (ev.country, ev.importance, ev.forecast, ev.actual) == ("USD", 3, 0.3, None)


def series(last_jump: float, n=600, seed=0):
    rng = np.random.default_rng(seed)
    vals = np.cumsum(rng.normal(0, 0.02, n))
    vals[-30:] += np.linspace(0, last_jump, 30)
    return pd.Series(vals, index=pd.bdate_range("2024-01-01", periods=n))


def test_component_score_sign_and_bounds():
    up = component_score(series(3.0), 63, sign=1)
    assert up == 2.0  # duzy wzrost, przyciety do +2
    assert component_score(series(3.0), 63, sign=-1) == -2.0
    assert abs(component_score(series(0.0), 63, sign=1)) < 2
    assert component_score(series(0.0).iloc[:20], 63, 1) is None


def test_compute_bias_tolerates_broken_series():
    def get(sid):
        if sid == "BAD":
            raise RuntimeError("404")
        return series(3.0 if sid == "UP" else -3.0)

    bias, details = compute_bias([{"series": "UP", "sign": -1}, {"series": "BAD"}, {"series": "DOWN", "sign": -1}], get)
    assert bias == 0.0 and details[1]["score"] is None and "error" in details[1]
    assert compute_bias([{"series": "BAD"}], get)[0] is None


def test_bias_store_and_staleness():
    conn = connect(":memory:")
    save_bias(conn, "GOLD", 1.2, [])
    assert read_bias(conn, "GOLD") == 1.2 and read_bias(conn, "OIL") is None
    old = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    conn.execute("UPDATE fundamental_bias SET updated=?", (old,))
    assert read_bias(conn, "GOLD") is None


def test_positioning_percentile():
    s = pd.Series(np.arange(100.0))
    assert positioning_percentile(s) == 100.0
    assert positioning_percentile(s.iloc[:5]) is None


def test_confluence():
    assert confluence(1, 2.0, 1).label == "mocny" and confluence(1, 2.0, 1).score == 3.0
    assert confluence(-1, 2.0, 1).label == "pod prad"
    c = confluence(1, None, 0)
    assert c.score == 1.0 and c.label == "neutralny" and "brak danych" in c.text
