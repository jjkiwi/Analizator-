from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import pandas as pd

from .base import DataSourceError, Throttle, normalize_candles

log = logging.getLogger(__name__)

# Yahoo trzyma dane godzinowe tylko 730 dni wstecz (sprawdzone: 729 dni dziala, 731 zwraca blad).
_INTRADAY_MAX_DAYS = 729
# Dane 30-minutowe: ok. 60 dni (wg dokumentacji yfinance; limit niesprawdzony na zywo).
_M30_MAX_DAYS = 59
# Tyle historii 1h pobieramy co najmniej przy swiecach 4h, zeby pewnie ustalic poczatek sesji.
_ANCHOR_LOOKBACK_DAYS = 60
_AGG = {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
_THROTTLE = Throttle(2.0)


class YahooAdapter:
    """yfinance to nieoficjalny klient Yahoo Finance: darmowy, opozniony, bywa zawodny.

    Konwencje indeksu (zawsze UTC):
    - 1d: data sesji gieldowej o 00:00 UTC (Yahoo podaje polnoc czasu gieldy, co po zamianie
      na UTC dawaloby 04:00/05:00 zaleznie od czasu letniego),
    - 1h, 30m: poczatek swiecy,
    - 4h: swiece liczone od otwarcia sesji w czasie gieldy (np. 18:00 Nowy Jork dla CME),
      a nie od polnocy UTC; patrz `resample_sessions`.
    """

    name = "yahoo"
    intervals = ("30m", "1h", "4h", "1d")

    def _download(self, source_symbol: str, yf_interval: str, start: datetime | None) -> pd.DataFrame:
        """Surowa odpowiedz yfinance: kolumny Open..Volume, indeks w strefie gieldy."""
        import yfinance as yf

        kwargs: dict = {"interval": yf_interval, "auto_adjust": False}
        if start:
            kwargs["start"] = start
        else:
            kwargs["period"] = "max"
        _THROTTLE.wait()
        try:
            raw = yf.Ticker(source_symbol).history(**kwargs)
        except Exception as exc:  # yfinance rzuca rozne typy
            raise DataSourceError(f"yahoo {source_symbol}: {exc}") from exc
        if raw is None or raw.empty:
            # yfinance przy nieznanym symbolu lub zakresie poza limitem tylko loguje blad i oddaje pusta ramke
            raise DataSourceError(
                f"yahoo {source_symbol} {yf_interval}: brak danych (zly symbol, zakres poza limitem albo blokada Yahoo)"
            )
        return raw

    def fetch(self, source_symbol: str, interval: str, start: datetime | None) -> pd.DataFrame:
        now = datetime.now(timezone.utc)
        if interval == "1d":
            return self._fetch_daily(source_symbol, start, now)
        if interval == "30m":
            floor = now - timedelta(days=_M30_MAX_DAYS)
            return shape_yahoo(self._download(source_symbol, "30m", max(start, floor) if start else floor), "30m", start)
        floor = now - timedelta(days=_INTRADAY_MAX_DAYS)
        dl_start = max(start, floor) if start else floor
        if interval == "4h":
            dl_start = max(min(dl_start, now - timedelta(days=_ANCHOR_LOOKBACK_DAYS)), floor)
        raw = self._download(source_symbol, "1h", dl_start)
        return shape_yahoo(raw, interval, start)

    def _fetch_daily(self, source_symbol: str, start: datetime | None, now: datetime) -> pd.DataFrame:
        # Niektore symbole (np. WIG20.WA) maja w Yahoo tylko dane intraday: zapytanie dzienne
        # konczy sie bledem albo oddaje sama biezaca sesje. Wtedy skladamy dni ze swiec 1h.
        expected = max((now - start).days * 5 // 7, 0) if start else 10_000
        min_rows = max(2, min(30, expected // 2))
        try:
            raw = self._download(source_symbol, "1d", start)
            if len(raw) >= min_rows:
                return shape_yahoo(raw, "1d", None)
            reason = f"tylko {len(raw)} swiec dziennych"
        except DataSourceError as exc:
            reason = str(exc)
        floor = now - timedelta(days=_INTRADAY_MAX_DAYS)
        hourly = self._download(source_symbol, "1h", max(start, floor) if start else floor)
        log.warning("yahoo %s: %s, skladam swiece dzienne z 1h (max %d dni)", source_symbol, reason, _INTRADAY_MAX_DAYS)
        return shape_yahoo(hourly, "1d_from_1h", None)


def shape_yahoo(raw: pd.DataFrame, interval: str, start: datetime | None = None) -> pd.DataFrame:
    """Zamienia surowa ramke yfinance na wspolny format. `interval`: 1d, 1h, 4h albo 1d_from_1h."""
    if raw is None or raw.empty:
        raise DataSourceError("yahoo: pusta odpowiedz")
    idx = pd.DatetimeIndex(raw.index)
    if idx.tz is None:
        idx = idx.tz_localize("UTC")
    raw = raw.set_axis(idx)
    if interval == "1d":
        raw = raw.set_axis(_session_dates(idx))
        return normalize_candles(raw)
    if interval in ("1h", "30m"):
        return normalize_candles(raw)
    local = normalize_candles(raw).tz_convert(idx.tz)
    if interval == "1d_from_1h":
        out = local.groupby(_session_dates(local.index)).agg(_AGG)
        return normalize_candles(out)
    if interval == "4h":
        out = resample_sessions(local, hours=4)
        # pierwsza swieca moze byc zlozona z niepelnych danych (pobieranie zaczyna sie w srodku okna)
        out = out.iloc[1:] if len(out) > 1 else out
        if start is not None:
            out = out[out.index >= pd.Timestamp(start).tz_convert("UTC")]
        return normalize_candles(out)
    raise ValueError(f"yahoo: nieobslugiwany interwal {interval}")


def _session_dates(idx: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """Data sesji w czasie gieldy, zapisana jako 00:00 UTC."""
    return idx.tz_localize(None).normalize().tz_localize("UTC")


def session_anchor_minutes(idx_local: pd.DatetimeIndex) -> int:
    """Minuta doby (czas gieldy), o ktorej zwykle zaczyna sie sesja: pierwsza swieca po przerwie.

    Rynek bez przerw (krypto) albo niejednoznaczny wynik daje 0, czyli okna od polnocy.
    """
    if len(idx_local) < 3:
        return 0
    gaps = idx_local.to_series().diff() > pd.Timedelta(hours=1)
    after = idx_local[gaps.to_numpy()]
    if len(after) < 3:
        return 0
    counts = pd.Series(after.hour * 60 + after.minute).value_counts()
    if counts.iloc[0] < 3 or counts.iloc[0] < 0.5 * len(after):
        return 0
    return int(counts.index[0])


def resample_sessions(df_local: pd.DataFrame, hours: int = 4, anchor_minutes: int | None = None) -> pd.DataFrame:
    """Sklada swiece 1h w `hours`-godzinne okna liczone od otwarcia sesji w czasie gieldy.

    Okna od polnocy UTC mieszalyby dla kontraktow CME koniec jednej sesji (do 17:00 NY)
    z poczatkiem nastepnej (od 18:00 NY) w jednej swiecy i przesuwaly sie o godzine przy zmianie czasu.
    Tu okna dla CME to 18-22, 22-02, 02-06, 06-10, 10-14, 14-17 czasu Nowego Jorku przez caly rok
    (ostatnie ma 3 godziny). Indeks wyniku: poczatek okna w UTC.
    """
    if df_local.index.tz is None:
        raise ValueError("resample_sessions wymaga indeksu ze strefa czasowa")
    if anchor_minutes is None:
        anchor_minutes = session_anchor_minutes(df_local.index)
    shift = pd.Timedelta(minutes=anchor_minutes)
    wall = df_local.index.tz_localize(None)
    bin_start = (wall - shift).floor(f"{hours}h") + shift
    work = df_local.copy()
    work["_utc"] = df_local.index.tz_convert("UTC")
    work["_wall"] = wall
    grouped = work.groupby(bin_start.to_numpy())
    out = grouped.agg({**_AGG, "_utc": "first", "_wall": "first"})
    # poczatek okna w UTC = czas pierwszej swiecy minus jej odleglosc od poczatku okna
    out.index = pd.DatetimeIndex(out["_utc"] - (out["_wall"] - out.index), name="time")
    return out.drop(columns=["_utc", "_wall"]).dropna(subset=["close"])


def resample_ohlcv(df: pd.DataFrame, rule: str) -> pd.DataFrame:
    """Prosty resampling w oknach kalendarzowych UTC (dla rynkow calodobowych)."""
    return df.resample(rule, label="left", closed="left").agg(_AGG).dropna(subset=["close"])
