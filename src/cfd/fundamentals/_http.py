"""Wspolne pobieranie HTTP dla adapterow fundamentow: uczciwy User-Agent, odstep miedzy zapytaniami, jasne bledy."""
from __future__ import annotations

import time
from urllib.parse import urlsplit

import httpx

from ..data.base import DataSourceError

# Uwaga: fred.stlouisfed.org zrywa polaczenie przy User-Agencie udajacym przegladarke ("Mozilla/... compatible").
USER_AGENT = "cfd-analyzer/0.2 (python-httpx)"

_last_request: dict[str, float] = {}


def http_get(url: str, params: dict | None = None, *, timeout: float = 60.0, min_interval: float = 3.0,
             retries: int = 2, accept: str = "*/*") -> httpx.Response:
    """GET z odstepem `min_interval` sekund na host i ponowieniem przy bledach transportu oraz 5xx.

    Zwraca odpowiedz takze dla 4xx (interpretuje ja adapter). `DataSourceError`, gdy serwis nie odpowiada.
    """
    host = urlsplit(url).netloc
    last_exc: Exception | None = None
    for attempt in range(retries + 1):
        wait = _last_request.get(host, 0.0) + min_interval - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        try:
            resp = httpx.get(url, params=params, timeout=timeout, follow_redirects=False,
                             headers={"User-Agent": USER_AGENT, "Accept": accept})
        except httpx.HTTPError as exc:
            last_exc = exc
            continue
        finally:
            _last_request[host] = time.monotonic()
        if resp.status_code >= 500 and attempt < retries:
            last_exc = DataSourceError(f"HTTP {resp.status_code}")
            continue
        return resp
    raise DataSourceError(f"{host}: brak odpowiedzi po {retries + 1} probach ({type(last_exc).__name__}: {last_exc})")
