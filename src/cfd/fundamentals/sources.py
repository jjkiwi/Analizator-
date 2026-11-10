from __future__ import annotations

import pandas as pd

from ..data.base import DataSourceError
from .cot import CotClient
from .eia import EiaClient
from .fred import FredClient


class SeriesRouter:
    """Jedno wejscie `series(id)` dla skladowych biasu. Prefiks wybiera zrodlo:

    `EIA:PET.WCESTUS1.W` -> EIA, `CFTC:disaggregated:088691` -> COT, bez prefiksu (lub `FRED:`) -> FRED.
    """

    def __init__(self, fred: FredClient | None = None, eia: EiaClient | None = None, cot: CotClient | None = None):
        self.fred = fred or FredClient()
        self.eia = eia or EiaClient()
        self.cot = cot or CotClient()

    def series(self, series_id: str) -> pd.Series:
        prefix, sep, rest = series_id.partition(":")
        if not sep:
            return self.fred.series(series_id)
        if prefix == "FRED":
            return self.fred.series(rest)
        if prefix == "EIA":
            return self.eia.series(rest)
        if prefix == "CFTC":
            return self.cot.series(rest)
        raise DataSourceError(f"Nieznane zrodlo serii: {series_id}")
