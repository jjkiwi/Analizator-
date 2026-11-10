from __future__ import annotations

import io
from datetime import datetime, timezone

import httpx
import pandas as pd

from .base import DataSourceError, normalize_candles


class StooqAdapter:
    """Zapasowe zrodlo swiec dziennych (CSV). Stooq potrafi limitowac pobrania."""

    name = "stooq"
    intervals = ("1d",)
    URL = "https://stooq.com/q/d/l/"

    def __init__(self, timeout: float = 20.0):
        self.timeout = timeout

    def fetch(self, source_symbol: str, interval: str, start: datetime | None) -> pd.DataFrame:
        params = {"s": source_symbol, "i": "d"}
        if start:
            params["d1"] = start.strftime("%Y%m%d")
            params["d2"] = datetime.now(timezone.utc).strftime("%Y%m%d")
        try:
            resp = httpx.get(self.URL, params=params, timeout=self.timeout, follow_redirects=True)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise DataSourceError(f"stooq {source_symbol}: {exc}") from exc
        text = resp.text
        if not text.lower().startswith("date"):
            # brak danych, limit pobran albo strona HTML zamiast CSV
            raise DataSourceError(f"stooq {source_symbol}: odpowiedz nie jest CSV ({text[:60]!r})")
        raw = pd.read_csv(io.StringIO(text), parse_dates=["Date"], index_col="Date")
        return normalize_candles(raw)
