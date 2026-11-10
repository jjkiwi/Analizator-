from __future__ import annotations

import os

import httpx
import pandas as pd


class FredClient:
    """API FRED (Fed w St. Louis). Darmowy klucz: zmienna FRED_API_KEY. Niesprawdzone w sieci."""

    URL = "https://api.stlouisfed.org/fred/series/observations"

    def __init__(self, api_key: str | None = None, timeout: float = 30.0):
        self.api_key = api_key or os.environ.get("FRED_API_KEY", "")
        self.timeout = timeout
        self._cache: dict[str, pd.Series] = {}

    def series(self, series_id: str, start: str = "2010-01-01") -> pd.Series:
        if series_id in self._cache:
            return self._cache[series_id]
        if not self.api_key:
            raise RuntimeError("Brak FRED_API_KEY")
        resp = httpx.get(
            self.URL,
            params={"series_id": series_id, "api_key": self.api_key, "file_type": "json", "observation_start": start},
            timeout=self.timeout,
        )
        resp.raise_for_status()
        obs = resp.json().get("observations", [])
        s = pd.Series(
            {pd.Timestamp(o["date"]): float(o["value"]) for o in obs if o.get("value") not in (None, "", ".")},
            dtype=float,
        ).sort_index()
        if s.empty:
            raise RuntimeError(f"FRED {series_id}: brak obserwacji")
        self._cache[series_id] = s
        return s
