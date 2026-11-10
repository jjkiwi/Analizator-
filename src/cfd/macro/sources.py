from __future__ import annotations

from datetime import datetime, timezone

import httpx

from .calendar import MacroEvent, parse_value

_IMPACT = {"high": 3, "medium": 2, "low": 1}


class FairEconomyCalendar:
    """Tygodniowy kalendarz makro w JSON (feed uzywany przez ForexFactory).

    NIESPRAWDZONE w sieci: adres i ksztalt danych zapisane z pamieci. Feed podaje prognoze
    i poprzedni odczyt, ale zwykle NIE podaje odczytu biezacego (`actual`), wiec reakcje
    "po publikacji" obsluguje na razie tor newsowy albo `cfd macro set-actual`.
    """

    name = "faireconomy"
    URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"

    def __init__(self, url: str | None = None, timeout: float = 20.0):
        self.url, self.timeout = url or self.URL, timeout

    def fetch(self) -> list[MacroEvent]:
        resp = httpx.get(self.url, timeout=self.timeout, follow_redirects=True,
                         headers={"User-Agent": "analizator-cfd/0.2"})
        resp.raise_for_status()
        return self.parse(resp.json())

    @staticmethod
    def parse(rows: list[dict]) -> list[MacroEvent]:
        out = []
        for row in rows:
            impact = _IMPACT.get(str(row.get("impact", "")).lower())
            if impact is None or not row.get("date") or not row.get("title"):
                continue  # swieta i wpisy bez godziny
            try:
                when = datetime.fromisoformat(str(row["date"]).replace("Z", "+00:00"))
            except ValueError:
                continue
            if when.tzinfo is None:
                when = when.replace(tzinfo=timezone.utc)
            out.append(
                MacroEvent(
                    time=when.astimezone(timezone.utc),
                    country=str(row.get("country", "")).upper(),
                    name=str(row["title"]).strip(),
                    importance=impact,
                    actual=parse_value(row.get("actual")),
                    forecast=parse_value(row.get("forecast")),
                    previous=parse_value(row.get("previous")),
                )
            )
        return out
