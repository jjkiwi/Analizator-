from __future__ import annotations

import logging
from datetime import datetime, timezone

import httpx
import pandas as pd

from .base import DataSourceError, Throttle, normalize_candles

log = logging.getLogger(__name__)
_THROTTLE = Throttle(0.3)


class BinanceAdapter:
    """Publiczne API Binance (bez klucza). Dane spot na zywo.

    `api.binance.com` odrzuca czesc lokalizacji (HTTP 451), dlatego jest zapasowy host
    z publicznymi danymi rynkowymi `data-api.binance.vision` (to samo API, te same swiece).
    """

    name = "binance"
    intervals = ("30m", "1h", "4h", "1d")
    HOSTS = ("https://api.binance.com", "https://data-api.binance.vision")
    PATH = "/api/v3/klines"
    PAGE = 1000

    def __init__(self, timeout: float = 20.0, max_pages: int = 200, hosts: tuple[str, ...] | None = None):
        self.timeout = timeout
        self.max_pages = max_pages  # 200 stron x 1000 swiec: ok. 22 lata swiec 1h
        self.hosts = list(hosts or self.HOSTS)

    def _get_page(self, client: httpx.Client, params: dict) -> list:
        """Jedna strona swiec. Przy niedostepnym hoscie przechodzi na nastepny i go zapamietuje."""
        errors = []
        for host in list(self.hosts):
            _THROTTLE.wait()
            try:
                resp = client.get(host + self.PATH, params=params)
            except httpx.HTTPError as exc:
                errors.append(f"{host}: {type(exc).__name__}: {exc}")
            else:
                if resp.status_code == 200:
                    if host != self.hosts[0]:  # dzialajacy host na poczatek, zeby nie pukac co strone w zablokowany
                        self.hosts.remove(host)
                        self.hosts.insert(0, host)
                    return parse_klines_page(resp.json())
                errors.append(f"{host}: HTTP {resp.status_code} {resp.text[:120]!r}")
                if resp.status_code == 400:  # zly symbol lub parametr: inny host odpowie tak samo
                    break
            log.info("binance: %s", errors[-1])
        raise DataSourceError(f"binance {params.get('symbol')}: {'; '.join(errors)}")

    def fetch(self, source_symbol: str, interval: str, start: datetime | None) -> pd.DataFrame:
        start_ms = int((start or datetime(2017, 1, 1, tzinfo=timezone.utc)).timestamp() * 1000)
        rows: list[list] = []
        with httpx.Client(timeout=self.timeout) as client:
            for _ in range(self.max_pages):
                page = self._get_page(
                    client,
                    {"symbol": source_symbol, "interval": interval, "startTime": start_ms, "limit": self.PAGE},
                )
                if not page:
                    break
                rows.extend(page)
                if len(page) < self.PAGE:
                    break
                start_ms = page[-1][0] + 1
            else:
                raise DataSourceError(f"binance {source_symbol}: historia dluzsza niz {self.max_pages} stron")
        if not rows:
            raise DataSourceError(f"binance {source_symbol}: brak danych")
        return klines_to_frame(rows)


def parse_klines_page(payload) -> list:
    """Sprawdza ksztalt odpowiedzi /klines: lista list [openTime, o, h, l, c, v, ...]."""
    if not isinstance(payload, list):
        raise DataSourceError(f"binance: nieoczekiwana odpowiedz {str(payload)[:120]!r}")
    if payload and (not isinstance(payload[0], list) or len(payload[0]) < 6):
        raise DataSourceError(f"binance: nieoczekiwany wiersz {str(payload[0])[:120]!r}")
    return payload


def klines_to_frame(rows: list) -> pd.DataFrame:
    raw = pd.DataFrame([r[:6] for r in rows], columns=["time", "open", "high", "low", "close", "volume"])
    raw.index = pd.to_datetime(raw.pop("time"), unit="ms", utc=True)
    return normalize_candles(raw)
