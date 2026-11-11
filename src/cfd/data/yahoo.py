from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd

from .base import DataSourceError, normalize_candles

# Yahoo ogranicza historie intraday: 1h ok. 730 dni, 30m ok. 60 dni.
_MAX_DAYS = {"1h": 729, "30m": 59}


class YahooAdapter:
    """yfinance to nieoficjalny klient Yahoo Finance: darmowy, opozniony, bywa zawodny."""

    name = "yahoo"
    intervals = ("30m", "1h", "4h", "1d")

    def fetch(self, source_symbol: str, interval: str, start: datetime | None) -> pd.DataFrame:
        import yfinance as yf

        now = datetime.now(timezone.utc)
        yf_interval = {"30m": "30m", "1h": "1h", "4h": "1h"}.get(interval, "1d")
        if yf_interval in _MAX_DAYS:
            floor = now - timedelta(days=_MAX_DAYS[yf_interval])
            start = max(start, floor) if start else floor
        kwargs = {"interval": yf_interval, "auto_adjust": False}
        if start:
            kwargs["start"] = start
        else:
            kwargs["period"] = "max"
        try:
            raw = yf.Ticker(source_symbol).history(**kwargs)
        except Exception as exc:  # yfinance rzuca rozne typy
            raise DataSourceError(f"yahoo {source_symbol}: {exc}") from exc
        df = normalize_candles(raw)
        if interval == "4h":
            df = resample_ohlcv(df, "4h")
        return df


def resample_ohlcv(df: pd.DataFrame, rule: str) -> pd.DataFrame:
    agg = {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    return df.resample(rule, label="left", closed="left").agg(agg).dropna(subset=["close"])
