from __future__ import annotations

import threading
import time
from datetime import datetime
from typing import Protocol

import pandas as pd

COLUMNS = ["open", "high", "low", "close", "volume"]
INTERVALS = ("30m", "1h", "4h", "1d")


class DataSourceError(RuntimeError):
    pass


class Throttle:
    """Wymusza minimalny odstep miedzy zapytaniami do jednego serwisu (zasada 3 z CLAUDE.md)."""

    def __init__(self, min_interval: float):
        self.min_interval = min_interval
        self._last = 0.0
        self._lock = threading.Lock()

    def wait(self) -> None:
        with self._lock:
            pause = self._last + self.min_interval - time.monotonic()
            if pause > 0:
                time.sleep(pause)
            self._last = time.monotonic()


class MarketDataAdapter(Protocol):
    name: str
    intervals: tuple[str, ...]

    def fetch(self, source_symbol: str, interval: str, start: datetime | None) -> pd.DataFrame:
        """Zwraca swiece OHLCV z indeksem czasowym UTC."""
        ...


def normalize_candles(df: pd.DataFrame) -> pd.DataFrame:
    """Wspolny format: indeks DatetimeIndex UTC rosnaco, kolumny OHLCV jako float."""
    if df is None or df.empty:
        raise DataSourceError("zrodlo zwrocilo pusty zbior")
    df = df.rename(columns=str.lower)
    missing = [c for c in COLUMNS[:4] if c not in df.columns]
    if missing:
        raise DataSourceError(f"brak kolumn: {missing}")
    if "volume" not in df.columns:
        df["volume"] = 0.0
    df = df[COLUMNS].astype(float)
    idx = pd.to_datetime(df.index, utc=True)
    df.index = idx
    df.index.name = "time"
    df = df[~df.index.duplicated(keep="last")].sort_index()
    df = df.dropna(subset=["open", "high", "low", "close"])
    bad = (df["high"] < df["low"]) | (df[["open", "high", "low", "close"]] <= 0).any(axis=1)
    df = df[~bad]
    if df.empty:
        raise DataSourceError("po walidacji nie zostala zadna swieca")
    return df
