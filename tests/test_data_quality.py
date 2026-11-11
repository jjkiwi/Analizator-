from pathlib import Path

import numpy as np
import pandas as pd

from cfd.data.quality import expiry_dates, find_gaps, find_jumps, format_reports, quality_report, roll_flags
from cfd.data.yahoo import shape_yahoo

FIX = Path(__file__).parent / "fixtures"


def flat(index, price=100.0):
    return pd.DataFrame(
        {"open": price, "high": price + 1, "low": price - 1, "close": price, "volume": 1.0}, index=index
    )


def test_daily_gaps_skip_weekends_and_holidays():
    idx = pd.bdate_range("2024-01-01", "2024-06-28", tz="UTC")
    idx = idx.drop(pd.Timestamp("2024-03-29", tz="UTC"))  # pojedyncze swieto
    assert find_gaps(idx, "1d") == []
    hole = idx[(idx < "2024-05-06") | (idx > "2024-05-10")]  # brak calego tygodnia
    gaps = find_gaps(hole, "1d")
    assert gaps == [(pd.Timestamp("2024-05-03", tz="UTC"), pd.Timestamp("2024-05-13", tz="UTC"))]


def test_crypto_gap_is_any_missing_bar():
    idx = pd.date_range("2024-01-01", periods=100, freq="1h", tz="UTC")
    assert find_gaps(idx, "1h", always_open=True) == []
    assert len(find_gaps(idx.delete(50), "1h", always_open=True)) == 1


def test_intraday_gaps_on_real_futures_sample():
    raw = pd.read_csv(FIX / "yahoo_CL=F_1h.csv", index_col=0)
    raw.index = pd.to_datetime(raw.index, utc=True).tz_convert("America/New_York")
    h1 = shape_yahoo(raw, "1h")
    # przerwa dobowa CME i weekendy nie sa lukami
    assert find_gaps(h1.index, "1h") == []
    broken = h1.drop(h1.index[(h1.index >= "2026-10-27 08:00") & (h1.index < "2026-10-27 14:00")])
    gaps = find_gaps(broken.index, "1h")
    assert len(gaps) == 1 and gaps[0][1] == pd.Timestamp("2026-10-27 14:00", tz="UTC")
    two_days = h1.drop(h1.index[(h1.index >= "2026-10-27") & (h1.index < "2026-10-30")])
    assert len(find_gaps(two_days.index, "1h")) == 1


def test_jumps_and_zero_range():
    idx = pd.bdate_range("2024-01-01", periods=60, tz="UTC")
    df = flat(idx)
    df.iloc[40:, :4] += 30.0  # skok o 30 przy ATR = 2
    df.iloc[10, df.columns.get_loc("high")] = df.iloc[10]["low"]
    rep = quality_report(df, "X", "1d")
    assert rep.bars == 60 and rep.zero_range == 1 and rep.gaps == []
    assert [t for t, _ in rep.jumps] == [idx[40]]
    assert abs(rep.jumps[0][1] - 15.0) < 1.0
    assert "X" in format_reports([rep]) and format_reports([rep], markdown=True).startswith("| symbol")


def test_jump_detection_is_causal():
    """Skok nie moze zalezec od pozniejszych swiec ani zawyzac wlasnego ATR."""
    idx = pd.bdate_range("2024-01-01", periods=80, tz="UTC")
    rng = np.random.default_rng(0)
    df = flat(idx)
    df[["open", "high", "low", "close"]] += rng.normal(0, 0.2, (80, 1))
    df.iloc[50:, :4] += 40.0
    full = find_jumps(df)
    assert full and find_jumps(df.iloc[:51]) == [j for j in full if j[0] <= idx[50]]


def test_roll_calendar_cl_and_ng():
    days = pd.bdate_range("2026-01-01", "2026-06-30", tz="UTC")
    cl = expiry_dates("CL=F", days)
    # WTI: 3 dni robocze przed 25. dniem miesiaca (25.01.2026 to niedziela -> liczymy od piatku 23.01)
    assert pd.Timestamp("2026-01-20", tz="UTC") in cl      # kontrakt lutowy
    assert pd.Timestamp("2026-03-20", tz="UTC") in cl      # 25.03 sroda -> 3 dni robocze wczesniej
    ng = expiry_dates("NG=F", days)
    assert pd.Timestamp("2026-01-28", tz="UTC") in ng      # 3. dzien roboczy od konca stycznia
    assert expiry_dates("GC=F", days) == []
    df = flat(days)
    flags = roll_flags(df, "CL=F")
    assert flags.sum() == len(cl) and flags.loc[pd.Timestamp("2026-01-21", tz="UTC")]
    assert not roll_flags(df, "ES=F").any()


def test_roll_calendar_ignores_incomplete_last_month():
    days = pd.bdate_range("2026-01-01", "2026-03-10", tz="UTC")
    assert max(expiry_dates("NG=F", days)).month == 2
    assert max(expiry_dates("CL=F", days)).month == 2
