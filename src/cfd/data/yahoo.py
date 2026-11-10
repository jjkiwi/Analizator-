from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd

from .base import DataSourceError, normalize_candles

# Yahoo trzyma dane godzinowe tylko ok. 730 dni wstecz.
_INTRADAY_MAX_DAYS = 729


class YahooAdapter:
    """yfinance to nieoficjalny klient Yahoo Finance: darmowy, opozniony, bywa zawodny."""

    name = "yahoo"
    intervals = ("1h", "4h", "1d")

    def fetch(self, source_symbol: str, interval: str, start: datetime | None) -> pd.DataFrame:
        import yfinance as yf

        now = datetime.now(timezone.utc)
        yf_interval = "1h" if interval in ("1h", "4h") else "1d"
        if yf_interval == "1h":
            floor = now - timedelta(days=_INTRADAY_MAX_DAYS)
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
