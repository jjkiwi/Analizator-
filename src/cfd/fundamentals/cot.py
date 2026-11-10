from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd

from ..data.base import DataSourceError
from ._http import http_get

# Raporty "futures only" w publicznym API CFTC (Socrata). Kolumny: grupa uznawana za spekulantow.
REPORTS: dict[str, dict[str, str]] = {
    "legacy": {"dataset": "6dca-aqww", "long": "noncomm_positions_long_all", "short": "noncomm_positions_short_all"},
    "disaggregated": {"dataset": "72hh-3qpy", "long": "m_money_positions_long_all", "short": "m_money_positions_short_all"},
    "tff": {"dataset": "gpe5-46if", "long": "lev_money_positions_long", "short": "lev_money_positions_short"},
}
DATE_FIELD = "report_date_as_yyyy_mm_dd"


def parse_cot_rows(rows, report: str, code: str) -> pd.Series:
    """Wiersze JSON z Socraty -> pozycja netto spekulantow (long minus short) po dacie raportu."""
    if isinstance(rows, dict):
        raise DataSourceError(f"CFTC {report}:{code}: {rows.get('message', 'nieoczekiwana odpowiedz')}")
    spec = REPORTS[report]
    data = {}
    for r in rows:
        try:
            data[pd.Timestamp(r[DATE_FIELD][:10])] = float(r[spec["long"]]) - float(r[spec["short"]])
        except (KeyError, TypeError, ValueError):
            continue
    s = pd.Series(data, dtype=float).sort_index()
    if s.empty:
        raise DataSourceError(f"CFTC {report}:{code}: brak raportow (zly kod kontraktu albo typ raportu?)")
    return s


class CotClient:
    """Raporty COT z CFTC (publicreporting.cftc.gov, bez klucza). Identyfikator: `<raport>:<kod kontraktu>`.

    Raport: `legacy` (non-commercial), `disaggregated` (managed money, surowce), `tff` (leveraged funds, finansowe).
    Raport wychodzi w piatek ze stanem na wtorek. Sprawdzone w sieci 2026-11-10.
    """

    BASE = "https://publicreporting.cftc.gov/resource/"

    def __init__(self, years: int = 5, timeout: float = 60.0):
        self.years = years
        self.timeout = timeout
        self._cache: dict[str, pd.Series] = {}

    def series(self, series_id: str) -> pd.Series:
        if series_id not in self._cache:
            report, _, code = series_id.partition(":")
            self._cache[series_id] = self.net_positions(code, report)
        return self._cache[series_id]

    def query(self, code: str, report: str) -> tuple[str, dict]:
        if report not in REPORTS:
            raise DataSourceError(f"CFTC: nieznany typ raportu '{report}' (dozwolone: {', '.join(REPORTS)})")
        if not code or not code.replace("+", "").isalnum():
            raise DataSourceError(f"CFTC: niepoprawny kod kontraktu '{code}'")
        spec = REPORTS[report]
        start = (datetime.now(timezone.utc) - timedelta(days=366 * self.years)).strftime("%Y-%m-%dT00:00:00.000")
        return self.BASE + spec["dataset"] + ".json", {
            "$select": f"{DATE_FIELD},{spec['long']},{spec['short']},open_interest_all",
            "$where": f"cftc_contract_market_code='{code}' AND {DATE_FIELD} >= '{start}'",
            "$order": f"{DATE_FIELD} ASC",
            "$limit": "5000",
        }

    def net_positions(self, code: str, report: str = "legacy") -> pd.Series:
        url, params = self.query(code, report)
        resp = http_get(url, params, timeout=self.timeout, min_interval=1.0)
        try:
            rows = resp.json()
        except ValueError:
            raise DataSourceError(f"CFTC {report}:{code}: HTTP {resp.status_code}, odpowiedz nie jest JSON-em") from None
        if resp.status_code != 200 and not isinstance(rows, dict):
            raise DataSourceError(f"CFTC {report}:{code}: HTTP {resp.status_code}")
        return parse_cot_rows(rows, report, code)
