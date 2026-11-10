"""Uzupelnianie odczytow biezacych (`actual`) z darmowych, publicznych zrodel urzedowych.

Kalendarz (faireconomy) nie podaje odczytu, wiec po godzinie publikacji pobieramy wlasciwa serie
statystyczna i sami liczymy wartosc w tej samej postaci, w jakiej kalendarz podaje prognoze
(np. zmiana m/m w %, zmiana zatrudnienia w osobach). Mapowanie wydarzenie -> seria jest w
`config/macro_rules.yaml` w sekcji `actuals`.

Dostawcy serii (kazdy zwraca `pd.Series` z indeksem dat okresu i rzuca `DataSourceError`):
- `FredCsvSeries`  fred.stlouisfed.org/graph/fredgraph.csv, bez klucza, sprawdzone na zywo
- `BlsSeries`      api.bls.gov (v2), bez klucza 25 zapytan/dobe na IP, z BLS_API_KEY 500/dobe
- `EiaDnavSeries`  publiczne strony historii serii www.eia.gov/dnav (zapasy ropy i gazu), bez klucza
"""
from __future__ import annotations

import csv
import io
import json
import logging
import os
import re
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Protocol

import pandas as pd
import yaml

from ..data.base import DataSourceError
from .calendar import MacroEvent
from .sources import http_text

log = logging.getLogger(__name__)


class SeriesProvider(Protocol):
    name: str

    def series(self, series_id: str) -> pd.Series:
        """Seria rosnaco po dacie okresu (poczatek miesiaca/kwartalu, koniec tygodnia). Blad: DataSourceError."""
        ...


class _Cached:
    """Pamiec podreczna serii na `ttl` sekund, zeby kilka wydarzen z jednej serii = jedno zapytanie."""

    ttl = 600.0

    def __init__(self) -> None:
        self._cache: dict[str, tuple[float, pd.Series]] = {}

    def series(self, series_id: str) -> pd.Series:
        hit = self._cache.get(series_id)
        if hit and time.monotonic() - hit[0] < self.ttl:
            return hit[1]
        s = self._fetch(series_id)
        if s.empty:
            raise DataSourceError(f"{self.name} {series_id}: brak obserwacji")
        s = s[~s.index.duplicated(keep="last")].sort_index()
        self._cache[series_id] = (time.monotonic(), s)
        return s

    def _fetch(self, series_id: str) -> pd.Series:  # pragma: no cover
        raise NotImplementedError


class FredCsvSeries(_Cached):
    """FRED bez klucza: plik CSV wykresu. Sprawdzone 2026-11-10: naglowek `observation_date,<ID>`,
    braki jako "." lub puste pole, nieznana seria = HTTP 404 (strona HTML). Opoznienie wzgledem publikacji:
    CPI z 13:30 UTC bylo w pliku o 14:12 UTC (naglowek last-modified), czyli ok. 40 minut."""

    name = "fred"
    URL = "https://fred.stlouisfed.org/graph/fredgraph.csv"

    def __init__(self, timeout: float = 60.0, history_days: int = 800):
        super().__init__()
        self.timeout, self.history_days = timeout, history_days

    def _fetch(self, series_id: str) -> pd.Series:
        start = (datetime.now(timezone.utc) - timedelta(days=self.history_days)).date().isoformat()
        text = http_text(self.URL, {"id": series_id, "cosd": start}, self.timeout, f"fred {series_id}")
        return self.parse(text, series_id)

    @staticmethod
    def parse(text: str, series_id: str) -> pd.Series:
        rows = list(csv.reader(io.StringIO(text)))
        if not rows or len(rows[0]) != 2 or rows[0][1].strip().upper() != series_id.upper():
            raise DataSourceError(f"fred {series_id}: nieoczekiwany format ({text[:60]!r})")
        out = {}
        for row in rows[1:]:
            if len(row) != 2 or row[1].strip() in ("", "."):
                continue
            try:
                out[pd.Timestamp(row[0])] = float(row[1])
            except ValueError:
                continue
        return pd.Series(out, dtype=float)


class BlsSeries(_Cached):
    """Publiczne API BLS v2 (GET, jedna seria na zapytanie). Odczyt jest dostepny w minucie publikacji.

    Limity (dokumentacja BLS): bez klucza 25 zapytan na dobe NA ADRES IP, z darmowym kluczem
    (BLS_API_KEY w .env, parametr `registrationkey`) 500 na dobe. Po wyczerpaniu serwer odpowiada
    HTTP 200 ze statusem REQUEST_NOT_PROCESSED: zamieniamy to na DataSourceError. Wlasny licznik w pliku
    `budget_path` pilnuje, zeby nie przekroczyc `daily_budget` zapytan na dobe.
    """

    name = "bls"
    URL = "https://api.bls.gov/publicAPI/v2/timeseries/data/"

    def __init__(self, api_key: str | None = None, timeout: float = 30.0, daily_budget: int | None = None,
                 budget_path: Path | str | None = "data/cache/macro/bls_budget.json"):
        super().__init__()
        self.api_key = api_key if api_key is not None else os.environ.get("BLS_API_KEY", "")
        self.timeout = timeout
        self.daily_budget = daily_budget if daily_budget is not None else (400 if self.api_key else 20)
        self.budget_path = Path(budget_path) if budget_path else None
        self._used: dict[str, int] = {}

    def _spend(self) -> None:
        today = datetime.now(timezone.utc).date().isoformat()
        used = self._used
        if self.budget_path is not None and self.budget_path.exists():
            try:
                used = json.loads(self.budget_path.read_text(encoding="utf-8"))
            except ValueError:
                used = {}
        count = int(used.get(today, 0))
        if count >= self.daily_budget:
            raise DataSourceError(f"bls: wyczerpany wlasny dzienny budzet zapytan ({self.daily_budget})")
        self._used = {today: count + 1}
        if self.budget_path is not None:
            self.budget_path.parent.mkdir(parents=True, exist_ok=True)
            self.budget_path.write_text(json.dumps(self._used), encoding="utf-8")

    def _fetch(self, series_id: str) -> pd.Series:
        self._spend()
        year = datetime.now(timezone.utc).year
        params = {"startyear": str(year - 2), "endyear": str(year)}
        if self.api_key:
            params["registrationkey"] = self.api_key
        text = http_text(self.URL + series_id, params, self.timeout, f"bls {series_id}")
        return self.parse(text, series_id)

    @staticmethod
    def parse(text: str, series_id: str) -> pd.Series:
        try:
            payload = json.loads(text)
        except ValueError as exc:
            raise DataSourceError(f"bls {series_id}: odpowiedz nie jest JSON-em") from exc
        if payload.get("status") != "REQUEST_SUCCEEDED":
            msg = "; ".join(payload.get("message") or []) or str(payload.get("status"))
            raise DataSourceError(f"bls {series_id}: {msg[:200]}")
        series = (payload.get("Results") or {}).get("series") or []
        data = series[0].get("data", []) if series else []
        out = {}
        for row in data:
            period = str(row.get("period", ""))
            if not re.fullmatch(r"M(0[1-9]|1[0-2])", period):
                continue  # M13 = srednia roczna, kwartalne/polroczne pomijamy
            try:
                out[pd.Timestamp(int(row["year"]), int(period[1:]), 1)] = float(row["value"])
            except (KeyError, ValueError):
                continue  # "-" = brak danych
        if not out:
            msg = "; ".join(payload.get("message") or [])
            raise DataSourceError(f"bls {series_id}: brak obserwacji miesiecznych {msg[:150]}")
        return pd.Series(out, dtype=float)


_MONTHS = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}
_EIA_ROW = re.compile(r"(\d{4})-([A-Za-z]{3})\s*</td>(.*?)</tr>", re.S)
_EIA_CELL = re.compile(r"class='B5'>\s*(\d\d)/(\d\d)(?:&nbsp;|\s)*</td>\s*<td class='B3'>\s*(-?[\d,]+(?:\.\d+)?)")


class EiaDnavSeries(_Cached):
    """Tygodniowe serie EIA z publicznych stron historii (www.eia.gov/dnav), bez klucza API.

    Identyfikator: "<dzial>:<seria>", np. "pet:WCESTUS1" (zapasy handlowe ropy, tys. bbl) albo
    "ng:NW2_EPG0_SWO_R48_BCF" (gaz w magazynach, Bcf). robots.txt zezwala na /dnav/; strona to jedna
    tabela: wiersz "RRRR-Mmm" i pary komorek data konca tygodnia (MM/DD) + wartosc.
    """

    name = "eia"
    URL = "https://www.eia.gov/dnav/{area}/hist/LeafHandler.ashx"

    def __init__(self, timeout: float = 60.0):
        super().__init__()
        self.timeout = timeout

    def _fetch(self, series_id: str) -> pd.Series:
        area, _, sid = series_id.partition(":")
        if area not in ("pet", "ng") or not sid:
            raise DataSourceError(f"eia: zly identyfikator serii {series_id!r} (oczekiwane pet:ID albo ng:ID)")
        text = http_text(self.URL.format(area=area), {"n": area.upper(), "s": sid, "f": "W"}, self.timeout, f"eia {sid}")
        return self.parse(text, series_id)

    @staticmethod
    def parse(text: str, series_id: str) -> pd.Series:
        out = {}
        for year, mon, body in _EIA_ROW.findall(text):
            month = _MONTHS.get(mon.lower())
            if month is None:
                continue
            for mm, dd, value in _EIA_CELL.findall(body):
                # wiersz jest przypisany do miesiaca konca tygodnia, wiec rok z wiersza pasuje do daty
                try:
                    out[pd.Timestamp(int(year), int(mm), int(dd))] = float(value.replace(",", ""))
                except ValueError:
                    continue
        if not out:
            raise DataSourceError(f"eia {series_id}: nie znaleziono tabeli z danymi (zmiana ukladu strony?)")
        return pd.Series(out, dtype=float)


# ---------- wydarzenie -> wartosc ----------

@dataclass(frozen=True)
class ActualRule:
    """Jak z serii policzyc odczyt dla wydarzenia z kalendarza.

    match      dokladne nazwy wydarzen (bez rozrozniania wielkosci liter), bo "CPI m/m" != "Core CPI m/m"
    sources    kolejne proby: [{"provider": "bls", "series": "..."}, {"provider": "fred", "series": "..."}]
    period     monthly | quarterly | weekly | daily: czestotliwosc serii
    lag        o ile okresow wstecz wzgledem daty publikacji lezy okres odczytu (miesieczne zwykle 1, JOLTS 2;
               dzienne: -1 = dzien po decyzji, bo np. nowy cel stopy Fed obowiazuje od nastepnego dnia)
    transform  level | diff | pct_change | pct_change_yoy
    scale      mnoznik do jednostki z kalendarza (np. 1000 dla serii w tysiacach)
    decimals   zaokraglenie jak w kalendarzu (1 = 0.1; -5 = do 100 tys.), zeby 0.249 nie bylo "niespodzianka" wobec 0.2
    """

    country: str
    match: tuple[str, ...]
    sources: tuple[tuple[str, str], ...]
    period: str = "monthly"
    lag: int = 1
    transform: str = "level"
    scale: float = 1.0
    decimals: int = 1

    @classmethod
    def from_dict(cls, d: dict) -> "ActualRule":
        rule = cls(
            country=str(d["country"]).upper(),
            match=tuple(str(m).strip().lower() for m in d["match"]),
            sources=tuple((str(s["provider"]), str(s["series"])) for s in d["sources"]),
            period=d.get("period", "monthly"), lag=int(d.get("lag", 1)),
            transform=d.get("transform", "level"), scale=float(d.get("scale", 1.0)), decimals=int(d.get("decimals", 1)),
        )
        if rule.period not in ("monthly", "quarterly", "weekly", "daily"):
            raise ValueError(f"actuals: nieznany period {rule.period!r}")
        if rule.transform not in ("level", "diff", "pct_change", "pct_change_yoy"):
            raise ValueError(f"actuals: nieznany transform {rule.transform!r}")
        return rule

    def matches(self, event: MacroEvent) -> bool:
        return event.country == self.country and event.name.strip().lower() in self.match


def load_actual_rules(path: Path | str = "config/macro_rules.yaml") -> list[ActualRule]:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    return [ActualRule.from_dict(d) for d in raw.get("actuals", [])]


def _month_shift(d: date, months: int) -> pd.Timestamp:
    idx = d.year * 12 + (d.month - 1) + months
    return pd.Timestamp(idx // 12, idx % 12 + 1, 1)


def target_period(series: pd.Series, event_time: datetime, period: str, lag: int) -> pd.Timestamp | None:
    """Data obserwacji, ktorej dotyczy publikacja z `event_time`, albo None, gdy seria jeszcze jej nie ma.

    To zabezpieczenie przed wpisaniem odczytu z POPRZEDNIEGO okresu, gdy zrodlo sie spoznia.
    """
    day = event_time.astimezone(timezone.utc).date()
    if period == "monthly":
        want = _month_shift(day, -lag)
    elif period == "quarterly":
        want = _month_shift(date(day.year, (day.month - 1) // 3 * 3 + 1, 1), -3 * lag)
    elif period == "daily":
        want = pd.Timestamp(day) - pd.Timedelta(days=lag)
    else:  # weekly: tydzien zakonczony w ciagu 8 dni przed publikacja (takze przy przesunieciu przez swieto)
        end = pd.Timestamp(day) - pd.Timedelta(days=7 * (lag - 1))
        window = series[(series.index < end) & (series.index >= end - pd.Timedelta(days=8))]
        return window.index[-1] if len(window) else None
    return want if want in series.index else None


def compute_actual(series: pd.Series, event_time: datetime, rule: ActualRule) -> float | None:
    """Odczyt w jednostce kalendarza albo None, gdy zrodlo nie ma jeszcze wlasciwego okresu."""
    when = target_period(series, event_time, rule.period, rule.lag)
    if when is None:
        return None
    pos = series.index.get_loc(when)
    value = float(series.iloc[pos])
    if rule.transform != "level":
        if rule.transform == "pct_change_yoy":
            base_date = _month_shift(when.date(), -12)
            if base_date not in series.index:
                raise DataSourceError(f"brak obserwacji sprzed roku ({base_date:%Y-%m})")
            base = float(series[base_date])
        else:
            if pos == 0:
                raise DataSourceError("brak poprzedniej obserwacji")
            gap = (when - series.index[pos - 1]).days
            if gap > {"monthly": 31, "quarterly": 92, "weekly": 7, "daily": 4}[rule.period]:
                raise DataSourceError(f"dziura w serii przed {when:%Y-%m-%d} (poprzednia obserwacja {gap} dni wczesniej)")
            base = float(series.iloc[pos - 1])
        if rule.transform == "diff":
            value = value - base
        else:
            if base == 0:
                raise DataSourceError("poprzednia obserwacja rowna 0")
            value = (value / base - 1.0) * 100.0
    return round(value * rule.scale, rule.decimals) + 0.0  # + 0.0: bez "-0.0"


@dataclass
class FillReport:
    filled: list[tuple[MacroEvent, str]] = field(default_factory=list)  # (wydarzenie z odczytem, "dostawca:seria")
    pending: list[MacroEvent] = field(default_factory=list)  # po terminie, zrodla nie maja jeszcze okresu
    errors: list[str] = field(default_factory=list)


class ActualsFiller:
    """Wpisuje `actual` do wydarzen po terminie. Nigdy nie rzuca wyjatku: bledy zrodel trafiaja do raportu."""

    def __init__(self, rules: list[ActualRule], providers: dict[str, SeriesProvider], max_age: timedelta = timedelta(days=8)):
        self.rules, self.providers, self.max_age = rules, providers, max_age
        self._resolved: dict[str, tuple[float, str]] = {}  # id wydarzenia -> (odczyt, zrodlo)
        self._broken: dict[str, str] = {}  # dostawca/seria, ktore zawiodly w tym przebiegu

    def rule_for(self, event: MacroEvent) -> ActualRule | None:
        return next((r for r in self.rules if r.matches(event)), None)

    def _value(self, event: MacroEvent, rule: ActualRule, report: FillReport) -> tuple[float, str] | None:
        for provider_name, series_id in rule.sources:
            key = f"{provider_name}:{series_id}"
            provider = self.providers.get(provider_name)
            if provider is None or key in self._broken:
                continue
            try:
                value = compute_actual(provider.series(series_id), event.time, rule)
            except DataSourceError as exc:
                self._broken[key] = str(exc)
                report.errors.append(f"{key}: {exc}")
                log.warning("macro actual %s: %s", key, exc)
                continue
            except Exception as exc:  # blad parsowania nie moze wywrocic odswiezania kalendarza
                self._broken[key] = str(exc)
                report.errors.append(f"{key}: {type(exc).__name__}: {exc}")
                log.warning("macro actual %s: %s: %s", key, type(exc).__name__, exc)
                continue
            if value is not None:
                return value, key
        return None

    def fill(self, events: list[MacroEvent], now: datetime | None = None) -> tuple[list[MacroEvent], FillReport]:
        now = now or datetime.now(timezone.utc)
        report = FillReport()
        self._broken = {}
        out = []
        for ev in events:
            rule = self.rule_for(ev) if ev.actual is None and now - self.max_age <= ev.time <= now else None
            if rule is None:
                out.append(ev)
                continue
            hit = self._resolved.get(ev.id) or self._value(ev, rule, report)
            if hit is None:
                report.pending.append(ev)
                out.append(ev)
                continue
            self._resolved[ev.id] = hit
            done = MacroEvent(ev.time, ev.country, ev.name, ev.importance, hit[0], ev.forecast, ev.previous, ev.unit)
            report.filled.append((done, hit[1]))
            out.append(done)
        return out, report


class CalendarWithActuals:
    """Zrodlo dla `cfd macro refresh` i `cfd run`: kalendarz + odczyty. Blad kalendarza = DataSourceError,
    blad zrodel odczytow = tylko wpis w `last_report.errors`."""

    name = "macro"

    def __init__(self, calendar, filler: ActualsFiller):
        self.calendar, self.filler = calendar, filler
        self.last_report = FillReport()

    def fetch(self, now: datetime | None = None) -> list[MacroEvent]:
        events = self.calendar.fetch()
        events, self.last_report = self.filler.fill(events, now)
        return events


def default_providers() -> dict[str, SeriesProvider]:
    return {"bls": BlsSeries(), "fred": FredCsvSeries(), "eia": EiaDnavSeries()}


def default_source(rules_path: Path | str = "config/macro_rules.yaml") -> CalendarWithActuals:
    """Kalendarz faireconomy z odczytami z BLS/FRED/EIA wedlug sekcji `actuals` w pliku regul."""
    from .sources import FairEconomyCalendar

    return CalendarWithActuals(FairEconomyCalendar(), ActualsFiller(load_actual_rules(rules_path), default_providers()))
