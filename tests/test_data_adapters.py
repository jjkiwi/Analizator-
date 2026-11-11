"""Testy adapterow swiec na zapisanych probkach prawdziwych odpowiedzi (bez sieci).

Probki z 2026-11-10: yahoo_*.csv to surowe ramki yfinance (indeks w strefie gieldy),
binance_*.json to odpowiedzi /api/v3/klines. Wyjatek: stooq_js_challenge_reconstructed.html
to rekonstrukcja strony weryfikacji przegladarki (Stooq zrywal polaczenie, zanim udalo sie zapisac oryginal).
"""
import json
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pandas as pd
import pytest

from cfd.data import DataSourceError
from cfd.data import binance as binance_mod
from cfd.data import yahoo as yahoo_mod
from cfd.data.binance import BinanceAdapter, klines_to_frame, parse_klines_page
from cfd.data.stooq import parse_stooq_csv
from cfd.data.yahoo import YahooAdapter, resample_sessions, session_anchor_minutes, shape_yahoo

FIX = Path(__file__).parent / "fixtures"
NY = "America/New_York"


def raw_yahoo(name: str, tz: str) -> pd.DataFrame:
    df = pd.read_csv(FIX / name, index_col=0)
    df.index = pd.to_datetime(df.index, utc=True).tz_convert(tz)
    return df


@pytest.fixture(autouse=True)
def no_throttle(monkeypatch):
    for mod in (yahoo_mod, binance_mod):
        monkeypatch.setattr(mod._THROTTLE, "min_interval", 0.0)


# ---------- Yahoo ----------

def test_yahoo_daily_index_is_session_date_utc():
    raw = raw_yahoo("yahoo_CL=F_1d.csv", NY)
    out = shape_yahoo(raw, "1d")
    assert str(out.index.tz) == "UTC" and len(out) == len(raw)
    # polnoc NY to 04:00 lub 05:00 UTC; po normalizacji zawsze 00:00 UTC z data sesji, takze po zmianie czasu
    assert (out.index == out.index.normalize()).all()
    assert out.index[-1] == pd.Timestamp("2026-11-06", tz="UTC")
    assert list(out.columns) == ["open", "high", "low", "close", "volume"]
    assert out.index.day_of_week.max() <= 4


def test_yahoo_hourly_is_utc_and_ordered():
    out = shape_yahoo(raw_yahoo("yahoo_CL=F_1h.csv", NY), "1h")
    assert str(out.index.tz) == "UTC" and out.index.is_monotonic_increasing and out.index.is_unique
    assert set(out.index.minute) == {0}


def test_yahoo_4h_anchored_to_session_open_across_dst():
    raw = raw_yahoo("yahoo_CL=F_1h.csv", NY)  # 19.10-06.11.2026, zmiana czasu w USA 1.11
    assert session_anchor_minutes(raw.index) == 18 * 60
    out = shape_yahoo(raw, "4h")
    local_hours = set(out.index.tz_convert(NY).hour)
    assert local_hours == {18, 22, 2, 6, 10, 14}  # te same godziny NY przed i po zmianie czasu
    assert {h for h in out.index[out.index < "2026-11-01"].hour} == {22, 2, 6, 10, 14, 18}  # UTC latem
    assert {h for h in out.index[out.index > "2026-11-02"].hour} == {23, 3, 7, 11, 15, 19}  # UTC zima
    # swieca 4h nie laczy dwoch sesji: zadna nie zawiera jednoczesnie godziny 16 i 18 NY
    h1 = shape_yahoo(raw, "1h")
    day = h1[(h1.index >= "2026-10-20 18:00") & (h1.index < "2026-10-20 21:00")]  # 14:00-17:00 NY
    bar = out.loc[pd.Timestamp("2026-10-20 18:00", tz="UTC")]
    assert bar["open"] == day["open"].iloc[0] and bar["close"] == day["close"].iloc[-1]
    assert bar["high"] == day["high"].max() and bar["volume"] == day["volume"].sum()


def test_resample_sessions_no_look_ahead():
    """Swieca 4h zalezy tylko od swiec 1h ze swojego okna: obciecie danych nie zmienia wczesniejszych swiec."""
    raw = raw_yahoo("yahoo_CL=F_1h.csv", NY)
    full = resample_sessions(shape_yahoo(raw, "1h").tz_convert(NY), anchor_minutes=1080)
    cut = resample_sessions(shape_yahoo(raw.iloc[:200], "1h").tz_convert(NY), anchor_minutes=1080)
    pd.testing.assert_frame_equal(cut.iloc[:-1], full.loc[cut.index[:-1]])


def test_yahoo_daily_built_from_hourly_when_daily_missing(monkeypatch):
    """WIG20.WA: Yahoo nie daje historii 1d (blad albo jedna swieca), wiec dni skladamy z 1h."""
    hourly = raw_yahoo("yahoo_WIG20.WA_1h.csv", "Europe/Warsaw")
    calls = []

    def fake(self, symbol, yf_interval, start):
        calls.append(yf_interval)
        if yf_interval == "1d":
            raise DataSourceError("yahoo WIG20.WA 1d: brak danych")
        return hourly

    monkeypatch.setattr(YahooAdapter, "_download", fake)
    out = YahooAdapter().fetch("WIG20.WA", "1d", None)
    assert calls == ["1d", "1h"]
    assert len(out) == len(set(hourly.index.date)) == 15
    last = hourly[hourly.index.date == hourly.index[-1].date()]
    assert out.index[-1] == pd.Timestamp("2026-11-06", tz="UTC")
    assert out["open"].iloc[-1] == last["Open"].iloc[0] and out["close"].iloc[-1] == last["Close"].iloc[-1]
    assert out["high"].iloc[-1] == last["High"].max()


def test_yahoo_empty_frame_is_clear_error(monkeypatch):
    import yfinance as yf

    monkeypatch.setattr(yf.Ticker, "history", lambda self, **kw: pd.DataFrame())
    with pytest.raises(DataSourceError, match="brak danych"):
        YahooAdapter().fetch("NOPE=F", "1h", None)


def test_yahoo_hourly_start_clamped_to_730_days(monkeypatch):
    seen = {}

    def fake(self, symbol, yf_interval, start):
        seen["start"] = start
        return raw_yahoo("yahoo_CL=F_1h.csv", NY)

    monkeypatch.setattr(YahooAdapter, "_download", fake)
    YahooAdapter().fetch("CL=F", "1h", datetime(2015, 1, 1, tzinfo=timezone.utc))
    assert (datetime.now(timezone.utc) - seen["start"]).days == 729


# ---------- Stooq ----------

def test_stooq_csv_parses():
    text = "Date,Open,High,Low,Close,Volume\n2026-11-05,4200.9,4254.9,4190.1,4209.1,1000\n2026-11-06,4166.3,4180.4,4120.0,4131.4,1200\n"
    out = parse_stooq_csv(text, "wig20")
    assert len(out) == 2 and out.index[-1] == pd.Timestamp("2026-11-06", tz="UTC") and out["close"].iloc[-1] == 4131.4


@pytest.mark.parametrize(
    "text, match",
    [
        ((FIX / "stooq_js_challenge_reconstructed.html").read_text(), "weryfikacji przegladarki"),
        ("<html><body>cos innego</body></html>", "HTML zamiast CSV"),
        ("Exceeded the daily hits limit", "limit"),
        ("No data", "brak danych"),
        ("", "brak danych"),
    ],
)
def test_stooq_non_csv_raises_clear_error(text, match):
    with pytest.raises(DataSourceError, match=match):
        parse_stooq_csv(text, "wig20")


# ---------- Binance ----------

def test_binance_klines_fixture_parses():
    page = parse_klines_page(json.loads((FIX / "binance_klines_BTCUSDT_1d.json").read_text()))
    out = klines_to_frame(page)
    assert len(out) == 8 and str(out.index.tz) == "UTC"
    assert out.index[0] == pd.Timestamp(page[0][0], unit="ms", tz="UTC")
    assert out["close"].iloc[0] == float(page[0][4]) and out["volume"].iloc[0] == float(page[0][5])
    assert (out.index == out.index.normalize()).all()


def test_binance_error_payload_rejected():
    with pytest.raises(DataSourceError):
        parse_klines_page(json.loads((FIX / "binance_451_restricted.json").read_text()))


def test_binance_falls_back_to_second_host(monkeypatch):
    restricted = (FIX / "binance_451_restricted.json").read_text()
    klines = (FIX / "binance_klines_BTCUSDT_1d.json").read_text()
    hits = []

    def handler(request: httpx.Request) -> httpx.Response:
        hits.append(request.url.host)
        if request.url.host == "api.binance.com":
            return httpx.Response(451, text=restricted)
        return httpx.Response(200, text=klines)

    orig = httpx.Client
    monkeypatch.setattr(binance_mod.httpx, "Client", lambda **kw: orig(transport=httpx.MockTransport(handler)))
    adapter = BinanceAdapter()
    out = adapter.fetch("BTCUSDT", "1d", None)
    assert len(out) == 8
    assert hits == ["api.binance.com", "data-api.binance.vision"]
    assert adapter.hosts[0] == "https://data-api.binance.vision"  # zapamietany dzialajacy host
    adapter.fetch("BTCUSDT", "1d", None)
    assert hits[2:] == ["data-api.binance.vision"]


def test_binance_all_hosts_down_raises(monkeypatch):
    restricted = (FIX / "binance_451_restricted.json").read_text()
    orig = httpx.Client
    monkeypatch.setattr(
        binance_mod.httpx, "Client",
        lambda **kw: orig(transport=httpx.MockTransport(lambda r: httpx.Response(451, text=restricted))),
    )
    with pytest.raises(DataSourceError, match="451"):
        BinanceAdapter().fetch("BTCUSDT", "1d", None)
