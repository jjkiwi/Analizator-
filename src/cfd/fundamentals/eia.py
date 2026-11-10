from __future__ import annotations

import html
import os
import re

import pandas as pd

from ..data.base import DataSourceError
from ._http import http_get

_ROW = re.compile(r"<td class='B6'>(.*?)</td>(.*?)</tr>", re.S | re.I)
_CELL = re.compile(r"<td class='B5'>(.*?)</td>\s*<td class='B3'>(.*?)</td>", re.S | re.I)


def _clean(cell: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", cell)).replace("\xa0", " ").strip()


def parse_eia_api(payload: dict, series_id: str) -> pd.Series:
    """Odpowiedz API v2 (`/v2/seriesid/<ID>`): `response.data[]` z polami `period` i `value` -> seria."""
    if "error" in payload:
        err = payload["error"]
        msg = f"{err.get('code', '')} {err.get('message', '')}".strip() if isinstance(err, dict) else str(err)
        raise DataSourceError(f"EIA {series_id}: {msg}")
    rows = (payload.get("response") or {}).get("data")
    if rows is None:
        raise DataSourceError(f"EIA {series_id}: nieoczekiwana odpowiedz API")
    data = {}
    for r in rows:
        try:
            data[pd.Timestamp(r["period"])] = float(r["value"])
        except (KeyError, TypeError, ValueError):
            continue
    s = pd.Series(data, dtype=float).sort_index()
    if s.empty:
        raise DataSourceError(f"EIA {series_id}: brak obserwacji")
    return s


def parse_eia_history_page(text: str, series_id: str) -> pd.Series:
    """Publiczna strona historii serii tygodniowej (www.eia.gov/dnav/.../hist/...) -> seria.

    Tabela: wiersz na miesiac ("2026-Oct"), w nim do pieciu par (data konca tygodnia "10/30", wartosc "409,760").
    """
    data: dict[pd.Timestamp, float] = {}
    for label, rest in _ROW.findall(text):
        m = re.match(r"(\d{4})-([A-Za-z]{3})", _clean(label))
        if not m:
            continue
        year = int(m.group(1))
        for date_cell, value_cell in _CELL.findall(rest):
            d, v = _clean(date_cell), _clean(value_cell).replace(",", "")
            dm = re.fullmatch(r"(\d{1,2})/(\d{1,2})", d)
            if not dm:
                continue
            try:
                data[pd.Timestamp(year=year, month=int(dm.group(1)), day=int(dm.group(2)))] = float(v)
            except ValueError:  # "NA", "W", "-" itp.
                continue
    s = pd.Series(data, dtype=float).sort_index()
    if len(s) < 10:
        raise DataSourceError(f"EIA {series_id}: nie rozpoznano tabeli historii (zmiana ukladu strony albo zla seria)")
    return s


def history_page_url(series_id: str) -> tuple[str, dict | None]:
    """Adres publicznej strony historii dla identyfikatora w stylu API v1, np. `PET.WCESTUS1.W`."""
    parts = series_id.split(".")
    if len(parts) != 3:
        raise DataSourceError(f"EIA {series_id}: oczekiwany format ZBIOR.SERIA.CZESTOTLIWOSC, np. PET.WCESTUS1.W")
    dataset, code, freq = parts
    if dataset.upper() == "PET":
        return "https://www.eia.gov/dnav/pet/hist/LeafHandler.ashx", {"n": "PET", "s": code.upper(), "f": freq.upper()}
    if dataset.upper() == "NG":
        return f"https://www.eia.gov/dnav/ng/hist/{code.lower()}{freq.lower()}.htm", None
    raise DataSourceError(f"EIA {series_id}: brak bezkluczowej sciezki dla zbioru {dataset}")


class EiaClient:
    """Serie tygodniowe EIA (zapasy ropy, benzyny, gazu). Identyfikatory jak w API v1: `PET.WCESTUS1.W`.

    Z kluczem `EIA_API_KEY`: API v2 (`api.eia.gov/v2/seriesid/<ID>`), niesprawdzone w sieci (brak klucza).
    Bez klucza albo gdy API zawiedzie: publiczna strona historii na www.eia.gov/dnav (dane rzadowe w domenie
    publicznej, robots.txt dopuszcza /dnav/), sprawdzona w sieci 2026-11-10. Jedno zapytanie na serie i przebieg.
    """

    API_URL = "https://api.eia.gov/v2/seriesid/"

    def __init__(self, api_key: str | None = None, timeout: float = 60.0):
        self.api_key = api_key if api_key is not None else os.environ.get("EIA_API_KEY", "")
        self.timeout = timeout
        self._cache: dict[str, pd.Series] = {}

    def series(self, series_id: str) -> pd.Series:
        if series_id not in self._cache:
            self._cache[series_id] = self._fetch(series_id)
        return self._cache[series_id]

    def _fetch(self, series_id: str) -> pd.Series:
        api_error = ""
        if self.api_key:
            try:
                return self._via_api(series_id)
            except DataSourceError as exc:
                api_error = f" (API: {exc})"
        try:
            return self._via_page(series_id)
        except DataSourceError as exc:
            raise DataSourceError(f"{exc}{api_error}") from None

    def _via_api(self, series_id: str) -> pd.Series:
        resp = http_get(self.API_URL + series_id, {"api_key": self.api_key}, timeout=self.timeout, min_interval=1.0)
        try:
            payload = resp.json()
        except ValueError:
            raise DataSourceError(f"EIA {series_id}: HTTP {resp.status_code}, odpowiedz nie jest JSON-em") from None
        return parse_eia_api(payload, series_id)

    def _via_page(self, series_id: str) -> pd.Series:
        url, params = history_page_url(series_id)
        resp = http_get(url, params, timeout=self.timeout, min_interval=5.0)
        if resp.status_code != 200:
            raise DataSourceError(f"EIA {series_id}: strona historii zwrocila HTTP {resp.status_code}")
        return parse_eia_history_page(resp.text, series_id)
