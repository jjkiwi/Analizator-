from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from cfd.validation.events import event_report, holidays_from_index, parse_current, parse_historical

FIX = Path(__file__).parent / "fixtures"


def test_parse_historical_2020_only_scheduled():
    d = parse_historical((FIX / "fomc_historical_2020.html").read_text())
    assert d == [date(2020, 1, 29), date(2020, 4, 29), date(2020, 6, 10), date(2020, 7, 29),
                 date(2020, 9, 16), date(2020, 11, 5), date(2020, 12, 16)]


def test_parse_current_2025_skips_notation_vote():
    d = parse_current((FIX / "fomc_calendars_2025.html").read_text(), date(2026, 1, 1))
    assert len(d) == 8 and d[0] == date(2025, 1, 29) and d[-1] == date(2025, 12, 10)
    assert date(2025, 8, 22) not in d


def test_holidays_from_index():
    idx = pd.bdate_range("2024-12-20", "2025-01-03").drop([pd.Timestamp("2024-12-25"), pd.Timestamp("2025-01-01")])
    assert holidays_from_index(idx) == [pd.Timestamp("2024-12-24"), pd.Timestamp("2024-12-31")]


def test_event_report_detects_effect():
    idx = pd.bdate_range("2000-01-03", periods=3000)
    rng = np.random.default_rng(0)
    r = pd.Series(rng.normal(0, 0.01, len(idx)), index=idx)
    ev = idx[::30]
    r[ev] += 0.01
    rep = event_report((1 + r).cumprod(), ev)
    assert rep["pass"] and rep["n"] == len(ev) - 1
