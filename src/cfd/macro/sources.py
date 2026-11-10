from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from ..data.base import DataSourceError
from .calendar import MacroEvent, parse_value

log = logging.getLogger(__name__)

USER_AGENT = "analizator-cfd/0.2"
_IMPACT = {"high": 3, "medium": 2, "low": 1}


_last_request: dict[str, float] = {}


def http_text(url: str, params: dict | None = None, timeout: float = 30.0, source: str = "http",
              min_interval: float = 3.0) -> str:
    """GET zwracajacy tresc; kazdy blad sieci i status != 200 zamienia na DataSourceError.

    Miedzy zapytaniami do tego samego hosta zachowuje odstep `min_interval` sekund.
    """
    host = urlsplit(url).netloc
    wait = _last_request.get(host, -1e9) + min_interval - time.monotonic()
    if wait > 0:
        time.sleep(wait)
    try:
        resp = httpx.get(url, params=params, timeout=timeout, follow_redirects=True, headers={"User-Agent": USER_AGENT})
    except httpx.HTTPError as exc:
        raise DataSourceError(f"{source}: blad sieci ({type(exc).__name__}: {exc})") from exc
    finally:
        _last_request[host] = time.monotonic()
    if resp.status_code == 429:
        raise DataSourceError(f"{source}: limit zapytan (HTTP 429, retry-after={resp.headers.get('retry-after', '?')} s)")
    if resp.status_code != 200:
        raise DataSourceError(f"{source}: HTTP {resp.status_code}")
    return resp.text


class FairEconomyCalendar:
    """Tygodniowy kalendarz makro w JSON (feed uzywany przez ForexFactory).

    Sprawdzone w sieci 2026-11-10: lista slownikow z polami title, country, date, impact, forecast, previous.
    - `date` to ISO 8601 z offsetem czasu nowojorskiego (-05:00 zima, -04:00 lato): przeliczamy na UTC.
    - impact: High / Medium / Low / Holiday (swieta pomijamy); country: kod waluty albo "All".
    - Feed NIE ma pola `actual`, takze po publikacji: odczyty uzupelnia `macro/actuals.py`.
    - Limit: po 5 zapytaniach w ok. 2 minuty serwer odpowiada HTTP 429 ("Rate Limited", retry-after ~200 s),
      a plik zmienia sie rzadko (kilka razy na dobe). Dlatego odpowiedz trafia do pliku cache i w ciagu
      `min_interval` sekund nie pytamy serwera ponownie; przy bledzie sieci uzywamy cache nie starszego
      niz `max_stale` sekund.
    """

    name = "faireconomy"
    URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"

    def __init__(self, url: str | None = None, timeout: float = 20.0,
                 cache_path: Path | str | None = "data/cache/macro/ff_calendar_thisweek.json",
                 min_interval: float = 600.0, max_stale: float = 24 * 3600.0):
        self.url, self.timeout = url or self.URL, timeout
        self.cache_path = Path(cache_path) if cache_path else None
        self.min_interval, self.max_stale = min_interval, max_stale
        self.from_cache = False  # czy ostatni fetch() obsluzono z pliku

    def _cache_age(self) -> float | None:
        if self.cache_path is None or not self.cache_path.exists():
            return None
        return max(time.time() - self.cache_path.stat().st_mtime, 0.0)

    def _read_cache(self) -> list[MacroEvent]:
        return self.parse(json.loads(self.cache_path.read_text(encoding="utf-8")))

    def fetch(self) -> list[MacroEvent]:
        age = self._cache_age()
        if age is not None and age < self.min_interval:
            try:
                self.from_cache = True
                return self._read_cache()
            except (ValueError, DataSourceError):
                pass  # uszkodzony plik: pobierz od nowa
        self.from_cache = False
        try:
            text = http_text(self.url, timeout=self.timeout, source=self.name)
            events = self.parse_text(text)
        except DataSourceError as exc:
            if age is not None and age < self.max_stale:
                log.warning("%s; uzywam kopii sprzed %.0f min", exc, age / 60)
                self.from_cache = True
                return self._read_cache()
            raise
        if self.cache_path is not None:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            self.cache_path.write_text(text, encoding="utf-8")
        return events

    @classmethod
    def parse_text(cls, text: str) -> list[MacroEvent]:
        try:
            rows = json.loads(text)
        except ValueError as exc:
            raise DataSourceError(f"{cls.name}: odpowiedz nie jest JSON-em ({text[:60]!r})") from exc
        if not isinstance(rows, list):
            raise DataSourceError(f"{cls.name}: oczekiwano listy, jest {type(rows).__name__}")
        events = cls.parse(rows)
        if not events:
            raise DataSourceError(f"{cls.name}: brak poprawnych wydarzen w odpowiedzi ({len(rows)} wierszy)")
        return events

    @staticmethod
    def parse(rows: list[dict]) -> list[MacroEvent]:
        out = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            impact = _IMPACT.get(str(row.get("impact", "")).lower())
            if impact is None or not row.get("date") or not row.get("title"):
                continue  # swieta i wpisy bez godziny
            try:
                when = datetime.fromisoformat(str(row["date"]).replace("Z", "+00:00"))
            except ValueError:
                continue
            if when.tzinfo is None:
                when = when.replace(tzinfo=timezone.utc)
            forecast = str(row.get("forecast") or "")
            out.append(
                MacroEvent(
                    time=when.astimezone(timezone.utc),
                    country=str(row.get("country", "")).upper(),
                    name=str(row["title"]).strip(),
                    importance=impact,
                    actual=parse_value(row.get("actual")),
                    forecast=parse_value(forecast),
                    previous=parse_value(row.get("previous")),
                    unit="%" if forecast.strip().endswith("%") else "",
                )
            )
        return out
