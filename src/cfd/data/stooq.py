from __future__ import annotations

import io
from datetime import datetime, timezone

import httpx
import pandas as pd

from .base import DataSourceError, Throttle, normalize_candles

_THROTTLE = Throttle(5.0)


class StooqAdapter:
    """Zapasowe zrodlo swiec dziennych (CSV). Stooq limituje pobrania i potrafi zadac weryfikacji przegladarki.

    Blokady nie obchodzimy: kazda odpowiedz inna niz CSV konczy sie jasnym DataSourceError.
    """

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
        _THROTTLE.wait()
        try:
            resp = httpx.get(self.URL, params=params, timeout=self.timeout, follow_redirects=True)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise DataSourceError(f"stooq {source_symbol}: {type(exc).__name__}: {exc}") from exc
        return parse_stooq_csv(resp.text, source_symbol)


def parse_stooq_csv(text: str, source_symbol: str = "?") -> pd.DataFrame:
    """Parsuje CSV ze Stooq. Rozpoznaje typowe odpowiedzi, ktore CSV nie sa."""
    head = text.lstrip("\ufeff \r\n\t")[:2000]
    low = head.lower()
    if low.startswith("date"):
        raw = pd.read_csv(io.StringIO(text.lstrip("\ufeff")), parse_dates=["Date"], index_col="Date")
        return normalize_candles(raw)
    if "<html" in low or "<!doctype" in low or "<script" in low:
        if "javascript" in low or "captcha" in low or "verify" in low:
            raise DataSourceError(
                f"stooq {source_symbol}: strona weryfikacji przegladarki (JavaScript/captcha) zamiast CSV; "
                "Stooq blokuje automatyczne pobieranie z tego adresu"
            )
        raise DataSourceError(f"stooq {source_symbol}: strona HTML zamiast CSV ({head[:60]!r})")
    if "exceeded the daily hits limit" in low or "przekroczony dzienny limit" in low:
        raise DataSourceError(f"stooq {source_symbol}: przekroczony dzienny limit pobran")
    if low.startswith("no data") or low.startswith("brak danych") or not low.strip():
        raise DataSourceError(f"stooq {source_symbol}: brak danych dla symbolu")
    raise DataSourceError(f"stooq {source_symbol}: odpowiedz nie jest CSV ({head[:60]!r})")
