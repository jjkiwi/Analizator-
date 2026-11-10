from __future__ import annotations

import io
import os

import pandas as pd

from ..data.base import DataSourceError
from ._http import http_get


def parse_fred_json(payload: dict, series_id: str) -> pd.Series:
    """Odpowiedz `fred/series/observations` (file_type=json) -> seria. Brakujace wartosci FRED oznacza kropka."""
    if "observations" not in payload:
        raise DataSourceError(f"FRED {series_id}: {payload.get('error_message', 'nieoczekiwana odpowiedz')}")
    s = pd.Series(
        {pd.Timestamp(o["date"]): float(o["value"]) for o in payload["observations"] if o.get("value") not in (None, "", ".")},
        dtype=float,
    ).sort_index()
    if s.empty:
        raise DataSourceError(f"FRED {series_id}: brak obserwacji")
    return s


def parse_fredgraph_csv(text: str, series_id: str) -> pd.Series:
    """Plik `fredgraph.csv` (naglowek `observation_date,<ID>`, puste pole = brak wartosci) -> seria."""
    head = text.lstrip()[:200].lower()
    if not head.startswith(("observation_date,", "date,")):
        raise DataSourceError(f"FRED {series_id}: odpowiedz nie jest plikiem CSV (seria nie istnieje?)")
    df = pd.read_csv(io.StringIO(text))
    if df.shape[1] < 2:
        raise DataSourceError(f"FRED {series_id}: CSV bez kolumny wartosci")
    values = pd.to_numeric(df.iloc[:, 1], errors="coerce")
    s = pd.Series(values.to_numpy(dtype=float), index=pd.to_datetime(df.iloc[:, 0])).dropna().sort_index()
    s.index.name = None
    if s.empty:
        raise DataSourceError(f"FRED {series_id}: brak obserwacji")
    return s


class FredClient:
    """Serie FRED (Fed w St. Louis).

    Z kluczem `FRED_API_KEY`: oficjalne API. Bez klucza: publiczny plik CSV wykresu
    (`fred.stlouisfed.org/graph/fredgraph.csv?id=...`), ten sam, ktory pobiera przycisk "Download" na stronie serii.
    Sciezka bezkluczowa sprawdzona w sieci 2026-11-10; sciezka z kluczem nadal niesprawdzona (brak klucza).
    """

    URL = "https://api.stlouisfed.org/fred/series/observations"
    CSV_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv"

    def __init__(self, api_key: str | None = None, timeout: float = 60.0):
        self.api_key = api_key if api_key is not None else os.environ.get("FRED_API_KEY", "")
        self.timeout = timeout
        self._cache: dict[str, pd.Series] = {}

    def series(self, series_id: str, start: str = "2010-01-01") -> pd.Series:
        if series_id not in self._cache:
            self._cache[series_id] = self._via_api(series_id, start) if self.api_key else self._via_csv(series_id, start)
        return self._cache[series_id]

    def _via_api(self, series_id: str, start: str) -> pd.Series:
        resp = http_get(
            self.URL,
            {"series_id": series_id, "api_key": self.api_key, "file_type": "json", "observation_start": start},
            timeout=self.timeout, min_interval=0.6,
        )
        try:
            payload = resp.json()
        except ValueError:
            raise DataSourceError(f"FRED {series_id}: HTTP {resp.status_code}, odpowiedz nie jest JSON-em") from None
        return parse_fred_json(payload, series_id)

    def _via_csv(self, series_id: str, start: str) -> pd.Series:
        resp = http_get(self.CSV_URL, {"id": series_id, "cosd": start}, timeout=self.timeout, min_interval=3.0, accept="text/csv,*/*")
        if resp.status_code == 404:
            raise DataSourceError(f"FRED {series_id}: seria nie istnieje (HTTP 404)")
        if resp.status_code != 200:
            raise DataSourceError(f"FRED {series_id}: HTTP {resp.status_code}")
        return parse_fredgraph_csv(resp.text, series_id)
