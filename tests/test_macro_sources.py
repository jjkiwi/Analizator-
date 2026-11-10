"""Adaptery makro na zapisanych probkach PRAWDZIWYCH odpowiedzi (tests/fixtures/macro, pobrane 2026-11-10)."""
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import pandas as pd
import pytest

from cfd.data import DataSourceError
from cfd.db import connect
from cfd.macro import (ActualsFiller, BlsSeries, CalendarWithActuals, EiaDnavSeries, FairEconomyCalendar, FredCsvSeries,
                       MacroEvent, MacroRules, load_actual_rules, surprise_effects, upsert_events)
from cfd.macro import sources as sources_mod
from cfd.macro.actuals import ActualRule, compute_actual, target_period
from cfd.macro.calendar import set_actual

FIX = Path(__file__).parent / "fixtures" / "macro"
ROOT = Path(__file__).parent.parent
UTC = timezone.utc
NOW = datetime(2026, 11, 10, 16, tzinfo=UTC)


def text(name: str) -> str:
    return (FIX / name).read_text(encoding="utf-8")


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """Domyslnie kazda proba wyjscia do sieci to blad testu; testy podstawiaja wlasne odpowiedzi."""
    def boom(*a, **k):
        raise AssertionError("test probuje uzyc sieci")
    monkeypatch.setattr(httpx, "get", boom)
    monkeypatch.setattr(sources_mod, "_last_request", {})
    monkeypatch.setattr(sources_mod.time, "sleep", lambda s: None)


def fake_get(monkeypatch, responses, calls=None):
    """responses: lista (status, tresc, naglowki) zwracanych po kolei (ostatnia powtarzana)."""
    queue = list(responses)

    def get(url, params=None, **kwargs):
        if calls is not None:
            calls.append((url, dict(params or {})))
        status, body, headers = queue.pop(0) if len(queue) > 1 else queue[0]
        return httpx.Response(status, text=body, headers=headers, request=httpx.Request("GET", url))
    monkeypatch.setattr(httpx, "get", get)


# ---------- D1: kalendarz ----------

def test_faireconomy_real_sample():
    events = FairEconomyCalendar.parse_text(text("ff_calendar_thisweek.json"))
    assert len(events) == 102  # 105 wierszy, 3 swieta ("Holiday") pominiete
    assert all(e.time.tzinfo is not None and e.time.utcoffset() == timedelta(0) for e in events)
    assert all(e.actual is None for e in events)  # feed nie ma pola actual, takze po publikacji
    cpi = next(e for e in events if e.name == "CPI m/m" and e.country == "USD")
    # w feedzie 08:30 czasu nowojorskiego (-05:00) = 13:30 UTC
    assert cpi.time == datetime(2026, 11, 10, 13, 30, tzinfo=UTC)
    assert (cpi.importance, cpi.forecast, cpi.previous, cpi.unit) == (3, 0.3, 0.6, "%")
    claims = next(e for e in events if e.name == "Unemployment Claims")
    assert (claims.importance, claims.forecast, claims.previous) == (2, 194000.0, 189000.0)
    crude = next(e for e in events if e.name == "Crude Oil Inventories")
    assert crude.forecast is None and crude.previous == -900000.0
    assert {e.country for e in events} >= {"USD", "EUR", "GBP", "JPY", "CNY", "ALL"}
    assert not any("Holiday" in e.name for e in events)


def test_faireconomy_summer_offset_and_garbage():
    (ev,) = FairEconomyCalendar.parse([{"title": "CPI m/m", "country": "USD", "date": "2026-07-14T08:30:00-04:00", "impact": "High"}])
    assert ev.time == datetime(2026, 7, 14, 12, 30, tzinfo=UTC)
    with pytest.raises(DataSourceError):
        FairEconomyCalendar.parse_text(text("ff_rate_limited.html"))
    with pytest.raises(DataSourceError):
        FairEconomyCalendar.parse_text("[]")
    with pytest.raises(DataSourceError):
        FairEconomyCalendar.parse_text('{"error": "x"}')


def test_faireconomy_rate_limit_without_cache_raises(monkeypatch, tmp_path):
    fake_get(monkeypatch, [(429, text("ff_rate_limited.html"), {"retry-after": "205"})])
    cal = FairEconomyCalendar(cache_path=tmp_path / "ff.json")
    with pytest.raises(DataSourceError, match="429.*205"):
        cal.fetch()
    assert not (tmp_path / "ff.json").exists()


def test_faireconomy_cache_limits_requests_and_survives_429(monkeypatch, tmp_path):
    calls = []
    fake_get(monkeypatch, [(200, text("ff_calendar_thisweek.json"), {}), (429, text("ff_rate_limited.html"), {"retry-after": "205"})], calls)
    cache = tmp_path / "macro" / "ff.json"
    cal = FairEconomyCalendar(cache_path=cache, min_interval=600)
    assert len(cal.fetch()) == 102 and not cal.from_cache
    assert len(cal.fetch()) == 102 and cal.from_cache  # drugi raz w ciagu 10 minut: bez zapytania
    assert len(calls) == 1
    old = time.time() - 3600
    os.utime(cache, (old, old))  # cache sprzed godziny: pytamy serwer, dostajemy 429, uzywamy kopii
    assert len(cal.fetch()) == 102 and cal.from_cache
    assert len(calls) == 2
    old = time.time() - 3 * 24 * 3600
    os.utime(cache, (old, old))  # kopia za stara: jasny blad zamiast nieaktualnych danych
    with pytest.raises(DataSourceError):
        cal.fetch()


def test_http_errors_become_datasource_error(monkeypatch):
    def timeout(url, **kwargs):
        raise httpx.ConnectTimeout("timeout")
    monkeypatch.setattr(httpx, "get", timeout)
    with pytest.raises(DataSourceError, match="blad sieci"):
        FairEconomyCalendar(cache_path=None).fetch()
    fake_get(monkeypatch, [(404, text("fred_404_head.html"), {})])
    with pytest.raises(DataSourceError, match="HTTP 404"):
        FredCsvSeries().series("NOSUCHSERIESX")


# ---------- D2: dostawcy serii ----------

def test_fred_csv_real_sample(monkeypatch):
    s = FredCsvSeries.parse(text("fred_CPIAUCSL.csv"), "CPIAUCSL")
    assert s.index.is_monotonic_increasing and s.index[-1] == pd.Timestamp("2026-10-01")
    assert s[pd.Timestamp("2026-09-01")] == 336.298 and s.iloc[-1] == 337.476
    assert FredCsvSeries.parse("observation_date,X\n2026-01-01,.\n2026-02-01,\n2026-03-01,5\n", "X").to_dict() == {pd.Timestamp("2026-03-01"): 5.0}
    with pytest.raises(DataSourceError):
        FredCsvSeries.parse(text("fred_404_head.html"), "CPIAUCSL")
    calls = []
    fake_get(monkeypatch, [(200, text("fred_ICSA.csv"), {})], calls)
    fred = FredCsvSeries()
    assert fred.series("ICSA").iloc[-1] == 189000.0
    fred.series("ICSA")  # z pamieci, bez drugiego zapytania
    assert len(calls) == 1 and calls[0][1]["id"] == "ICSA" and "cosd" in calls[0][1]
    fake_get(monkeypatch, [(200, "observation_date,ICSA\n", {})])
    with pytest.raises(DataSourceError, match="brak obserwacji"):
        FredCsvSeries().series("ICSA")


def test_bls_real_samples():
    s = BlsSeries.parse(text("bls_LNS14000000_latest.json"), "LNS14000000")
    assert s.to_dict() == {pd.Timestamp("2026-10-01"): 4.1}
    with pytest.raises(DataSourceError, match="daily threshold"):
        BlsSeries.parse(text("bls_threshold.json"), "CUSR0000SA0")
    with pytest.raises(DataSourceError):
        BlsSeries.parse("<html>", "X")
    # ksztalt pelnej odpowiedzi wg dokumentacji BLS (atrapa: limit dzienny nie pozwolil pobrac probki wielomiesiecznej)
    doc = ('{"status":"REQUEST_SUCCEEDED","message":[],"Results":{"series":[{"seriesID":"X","data":['
           '{"year":"2026","period":"M13","value":"9"},{"year":"2026","period":"M02","value":"-"},'
           '{"year":"2026","period":"M01","value":"2.5"},{"year":"2025","period":"M12","value":"2.0"}]}]}}')
    assert BlsSeries.parse(doc, "X").to_dict() == {pd.Timestamp("2025-12-01"): 2.0, pd.Timestamp("2026-01-01"): 2.5}


def test_bls_key_from_env_and_daily_budget(monkeypatch, tmp_path):
    calls = []
    fake_get(monkeypatch, [(200, text("bls_LNS14000000_latest.json"), {})], calls)
    monkeypatch.delenv("BLS_API_KEY", raising=False)
    bls = BlsSeries(daily_budget=2, budget_path=tmp_path / "b.json")
    bls.series("LNS14000000")
    assert calls[0][0].endswith("/timeseries/data/LNS14000000") and "registrationkey" not in calls[0][1]
    bls.series("LNS14000000")  # z pamieci: nie zuzywa budzetu
    bls.series("OTHER1")
    with pytest.raises(DataSourceError, match="budzet"):
        bls.series("OTHER2")
    assert len(calls) == 2
    with pytest.raises(DataSourceError, match="budzet"):  # licznik jest w pliku, wiec przezywa restart procesu
        BlsSeries(daily_budget=2, budget_path=tmp_path / "b.json").series("OTHER3")
    monkeypatch.setenv("BLS_API_KEY", "tajny-klucz")
    keyed = BlsSeries(budget_path=None)
    keyed.series("LNS14000000")
    assert calls[-1][1]["registrationkey"] == "tajny-klucz" and keyed.daily_budget == 400
    fake_get(monkeypatch, [(200, text("bls_threshold.json"), {})])
    with pytest.raises(DataSourceError, match="daily threshold") as err:
        BlsSeries(budget_path=None).series("CUSR0000SA0")
    assert "tajny-klucz" not in str(err.value)


def test_eia_dnav_real_samples(monkeypatch):
    crude = EiaDnavSeries.parse(text("eia_pet_WCESTUS1.html"), "pet:WCESTUS1")
    assert crude.index[0] == pd.Timestamp("2026-01-02") and crude.index[-1] == pd.Timestamp("2026-10-30")
    assert crude[pd.Timestamp("2026-10-30")] == 409760.0 and crude[pd.Timestamp("2026-10-23")] == 410625.0
    assert (crude.index.day_of_week == 4).all() and len(crude) == 44  # same piatki
    gas = EiaDnavSeries.parse(text("eia_ng_NW2_EPG0_SWO_R48_BCF.html"), "ng:NW2_EPG0_SWO_R48_BCF")
    assert gas[pd.Timestamp("2026-10-30")] == 3801.0 and gas[pd.Timestamp("2026-10-23")] == 3724.0
    with pytest.raises(DataSourceError, match="tabeli"):
        EiaDnavSeries.parse("<html><body>Maintenance</body></html>", "pet:WCESTUS1")
    with pytest.raises(DataSourceError, match="identyfikator"):
        EiaDnavSeries().series("WCESTUS1")
    calls = []
    fake_get(monkeypatch, [(200, text("eia_pet_WCESTUS1.html"), {})], calls)
    EiaDnavSeries().series("pet:WCESTUS1")
    assert calls[0] == ("https://www.eia.gov/dnav/pet/hist/LeafHandler.ashx", {"n": "PET", "s": "WCESTUS1", "f": "W"})


# ---------- D2: wydarzenie -> odczyt ----------

class FixtureProvider:
    """Dostawca czytajacy probki z dysku; liczy zapytania."""

    def __init__(self, name, parser, files, fail=None):
        self.name, self.parser, self.files, self.fail, self.calls = name, parser, files, fail, []

    def series(self, series_id):
        self.calls.append(series_id)
        if self.fail:
            raise DataSourceError(self.fail)
        if series_id not in self.files:
            raise DataSourceError(f"{self.name} {series_id}: HTTP 404")
        return self.parser(text(self.files[series_id]), series_id).sort_index()


def providers(bls_fail="bls: daily threshold has been reached"):
    return {
        "bls": FixtureProvider("bls", BlsSeries.parse, {}, fail=bls_fail),
        "fred": FixtureProvider("fred", FredCsvSeries.parse, {s: f"fred_{s}.csv" for s in ("CPIAUCSL", "CPIAUCNS", "PAYEMS", "ICSA", "A191RL1Q225SBEA")}),
        "eia": FixtureProvider("eia", EiaDnavSeries.parse, {"pet:WCESTUS1": "eia_pet_WCESTUS1.html", "ng:NW2_EPG0_SWO_R48_BCF": "eia_ng_NW2_EPG0_SWO_R48_BCF.html"}),
    }


def rules():
    return load_actual_rules(ROOT / "config" / "macro_rules.yaml")


def rule(name):
    return next(r for r in rules() if name.lower() in r.match)


def test_config_actual_rules_are_consistent():
    rs = rules()
    assert len(rs) >= 15
    names = [m for r in rs for m in r.match]
    assert len(names) == len(set(names))  # jedno wydarzenie = jedna regula
    assert all(p in ("bls", "fred", "eia") for r in rs for p, _ in r.sources)
    MacroRules.from_file(ROOT / "config" / "macro_rules.yaml")  # sekcja `actuals` nie psuje regul reakcji
    with pytest.raises(ValueError):
        ActualRule.from_dict({"country": "USD", "match": ["x"], "sources": [], "transform": "magia"})


def test_compute_actual_matches_calendar_previous():
    """Kontrola krzyzowa: wartosci policzone z serii dla POPRZEDNICH publikacji = pole `previous` z kalendarza."""
    p = providers()
    cpi = p["fred"].series("CPIAUCSL")
    assert compute_actual(cpi, datetime(2026, 10, 14, 12, 30, tzinfo=UTC), rule("CPI m/m")) == 0.6
    assert compute_actual(cpi, datetime(2026, 11, 10, 13, 30, tzinfo=UTC), rule("CPI m/m")) == 0.4
    nsa = p["fred"].series("CPIAUCNS")
    assert compute_actual(nsa, datetime(2026, 10, 14, 12, 30, tzinfo=UTC), rule("CPI y/y")) == 3.7  # 336.940 / 324.800
    # prawdziwa dziura w danych: indeksu CPI za pazdziernik 2025 nie opublikowano, wiec r/r za 10.2026
    # nie da sie policzyc z serii; ma byc jawny blad, a nie wynik liczony wzgledem innego miesiaca
    with pytest.raises(DataSourceError, match="sprzed roku"):
        compute_actual(nsa, datetime(2026, 11, 10, 13, 30, tzinfo=UTC), rule("CPI y/y"))
    claims = p["fred"].series("ICSA")
    assert compute_actual(claims, datetime(2026, 11, 5, 13, 30, tzinfo=UTC), rule("Unemployment Claims")) == 189000.0
    crude = p["eia"].series("pet:WCESTUS1")
    assert compute_actual(crude, datetime(2026, 11, 4, 15, 30, tzinfo=UTC), rule("Crude Oil Inventories")) == -900000.0
    gas = p["eia"].series("ng:NW2_EPG0_SWO_R48_BCF")
    assert compute_actual(gas, datetime(2026, 11, 5, 15, 30, tzinfo=UTC), rule("Natural Gas Storage")) == 77e9
    with pytest.raises(DataSourceError, match="dziura"):  # m/m za 11.2025 nie moze byc liczone wzgledem 09.2025
        compute_actual(nsa, datetime(2025, 12, 18, 13, 30, tzinfo=UTC), rule("CPI m/m"))
    nfp = compute_actual(p["fred"].series("PAYEMS"), datetime(2026, 11, 6, 13, 30, tzinfo=UTC), rule("Non-Farm Employment Change"))
    assert nfp == 165000.0  # 159293 - 159128 tys.
    gdp = p["fred"].series("A191RL1Q225SBEA")
    assert compute_actual(gdp, datetime(2026, 10, 29, 12, 30, tzinfo=UTC), rule("Advance GDP q/q")) == 3.4
    assert compute_actual(gdp, datetime(2026, 12, 22, 13, 30, tzinfo=UTC), rule("Final GDP q/q")) == 3.4


def test_no_stale_period_is_used():
    """Zrodlo bez nowego okresu daje None, a nie odczyt z poprzedniego miesiaca/tygodnia."""
    p = providers()
    cpi = p["fred"].series("CPIAUCSL").iloc[:-1]  # stan sprzed publikacji: ostatni jest wrzesien
    assert compute_actual(cpi, datetime(2026, 11, 10, 13, 30, tzinfo=UTC), rule("CPI m/m")) is None
    claims = p["fred"].series("ICSA")  # ostatni tydzien w probce: 31.10; publikacja 12.11 dotyczy 7.11
    assert compute_actual(claims, datetime(2026, 11, 12, 13, 30, tzinfo=UTC), rule("Unemployment Claims")) is None
    crude = p["eia"].series("pet:WCESTUS1")
    assert compute_actual(crude, datetime(2026, 11, 12, 17, 0, tzinfo=UTC), rule("Crude Oil Inventories")) is None
    s = pd.Series({pd.Timestamp("2026-11-06"): 1.0, pd.Timestamp("2026-11-13"): 2.0})
    # tydzien zakonczony w dniu publikacji lub pozniej nie moze byc "odczytem" tej publikacji
    assert target_period(s, datetime(2026, 11, 13, 15, 30, tzinfo=UTC), "weekly", 1) == pd.Timestamp("2026-11-06")
    daily = pd.Series({pd.Timestamp("2026-11-04"): 4.0, pd.Timestamp("2026-11-05"): 3.75})
    fed = rule("Federal Funds Rate")
    assert compute_actual(daily, datetime(2026, 11, 4, 19, 0, tzinfo=UTC), fed) == 3.75
    assert compute_actual(daily.iloc[:1], datetime(2026, 11, 4, 19, 0, tzinfo=UTC), fed) is None
    assert compute_actual(pd.Series({pd.Timestamp("2026-09-01"): 7523.0}), datetime(2026, 11, 3, 15, tzinfo=UTC), rule("JOLTS Job Openings")) == 7520000.0


def test_filler_falls_back_and_never_raises():
    events = FairEconomyCalendar.parse_text(text("ff_calendar_thisweek.json"))
    p = providers()
    filler = ActualsFiller(rules(), p)
    out, report = filler.fill(events, NOW)
    assert len(out) == len(events)
    filled = {e.name: (e.actual, src) for e, src in report.filled}
    assert filled["CPI m/m"] == (0.4, "fred:CPIAUCSL")  # BLS z limitem -> FRED
    assert any("bls:CUSR0000SA0" in e and "daily threshold" in e for e in report.errors)
    assert "Core CPI m/m" in [e.name for e in report.pending]  # brak probki CPILFESL = zrodlo zawiodlo, czekamy
    assert all(e.time <= NOW for e, _ in report.filled) and all(e.time > NOW for e in out if e.name == "PPI m/m")
    # przyszle wydarzenia nie dostaja odczytu i nie generuja zapytan
    assert not any(e.actual is not None and e.time > NOW for e in out)
    assert "ICSA" not in p["fred"].calls and p["eia"].calls == []
    # drugi przebieg: wynik z pamieci, bez ponownego pytania o CPIAUCSL
    n = p["fred"].calls.count("CPIAUCSL")
    out2, report2 = filler.fill(events, NOW)
    assert p["fred"].calls.count("CPIAUCSL") == n and [e.actual for e in out2] == [e.actual for e in out]
    # wszystkie zrodla martwe: zadnego wyjatku, same wpisy w raporcie
    dead = {k: FixtureProvider(k, None, {}, fail="padlo") for k in ("bls", "fred", "eia")}
    out3, report3 = ActualsFiller(rules(), dead).fill(events, NOW)
    assert report3.filled == [] and report3.errors and all(e.actual is None for e in out3)

    class Buggy:
        name = "fred"

        def series(self, sid):
            raise KeyError("niespodziewany blad parsera")
    out4, report4 = ActualsFiller(rules(), {"fred": Buggy()}).fill(events, NOW)
    assert report4.filled == [] and any("KeyError" in e for e in report4.errors)


def test_calendar_with_actuals_end_to_end():
    class Cal:
        from_cache = False

        def fetch(self):
            return FairEconomyCalendar.parse_text(text("ff_calendar_thisweek.json"))

    source = CalendarWithActuals(Cal(), ActualsFiller(rules(), providers()))
    conn = connect(":memory:")
    upsert_events(conn, source.fetch(NOW))
    row = conn.execute("SELECT * FROM macro_events WHERE name='CPI m/m' AND country='USD'").fetchone()
    assert (row["actual"], row["forecast"], row["alerted_after"]) == (0.4, 0.3, 0)
    macro_rules = MacroRules.from_file(ROOT / "config" / "macro_rules.yaml")
    ev = MacroEvent(datetime.fromisoformat(row["time"]), "USD", "CPI m/m", 3, row["actual"], row["forecast"])
    assert surprise_effects(ev, macro_rules) == {"US500": -1, "US100": -1, "GOLD": -1, "USDIDX": 1}

    class Broken:
        def fetch(self):
            raise DataSourceError("faireconomy: HTTP 429")
    with pytest.raises(DataSourceError):  # padniety kalendarz to jawny blad (runner zapisuje go w health)
        CalendarWithActuals(Broken(), ActualsFiller(rules(), providers())).fetch(NOW)


def test_upsert_keeps_manual_actual():
    conn = connect(":memory:")
    t = datetime(2026, 11, 10, 13, 30, tzinfo=UTC)
    upsert_events(conn, [MacroEvent(t, "USD", "CPI m/m", 3, forecast=0.3)])
    set_actual(conn, "cpi m/m", 0.5, NOW)
    upsert_events(conn, [MacroEvent(t, "USD", "CPI m/m", 3, actual=0.4, forecast=0.3)])
    assert conn.execute("SELECT actual FROM macro_events").fetchone()[0] == 0.5
    set_actual(conn, "cpi m/m", 0.4, NOW)  # reczna poprawka zawsze dziala
    assert conn.execute("SELECT actual FROM macro_events").fetchone()[0] == 0.4
