from __future__ import annotations

from datetime import datetime, timezone

import httpx
import pandas as pd

from .base import DataSourceError, normalize_candles


class BinanceAdapter:
    """Publiczne API Binance (bez klucza). Dane spot na zywo."""

    name = "binance"
    intervals = ("1h", "4h", "1d")
    URL = "https://api.binance.com/api/v3/klines"
    PAGE = 1000

    def __init__(self, timeout: float = 20.0, max_pages: int = 60):
        self.timeout = timeout
        self.max_pages = max_pages

    def fetch(self, source_symbol: str, interval: str, start: datetime | None) -> pd.DataFrame:
        start_ms = int((start or datetime(2017, 1, 1, tzinfo=timezone.utc)).timestamp() * 1000)
        rows: list[list] = []
        try:
            with httpx.Client(timeout=self.timeout) as client:
                for _ in range(self.max_pages):
                    resp = client.get(
                        self.URL,
                        params={
                            "symbol": source_symbol,
                            "interval": interval,
                            "startTime": start_ms,
                            "limit": self.PAGE,
                        },
                    )
                    resp.raise_for_status()
                    page = resp.json()
                    if not page:
                        break
                    rows.extend(page)
                    if len(page) < self.PAGE:
                        break
                    start_ms = page[-1][0] + 1
        except httpx.HTTPError as exc:
            raise DataSourceError(f"binance {source_symbol}: {exc}") from exc
        if not rows:
            raise DataSourceError(f"binance {source_symbol}: brak danych")
        raw = pd.DataFrame(
            [r[:6] for r in rows], columns=["time", "open", "high", "low", "close", "volume"]
        )
        raw.index = pd.to_datetime(raw.pop("time"), unit="ms", utc=True)
        return normalize_candles(raw)
