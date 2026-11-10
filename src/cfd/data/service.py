from __future__ import annotations

import logging
from datetime import timedelta

import pandas as pd

from ..models import Instrument
from .base import INTERVALS, DataSourceError, MarketDataAdapter
from .store import CandleStore

log = logging.getLogger(__name__)

# Kolejnosc = priorytet. Pierwsze zrodlo, ktore zadziala, wygrywa.
SOURCE_PRIORITY = ("binance", "yahoo", "stooq")


def default_adapters() -> dict[str, MarketDataAdapter]:
    from .binance import BinanceAdapter
    from .stooq import StooqAdapter
    from .yahoo import YahooAdapter

    return {a.name: a for a in (BinanceAdapter(), YahooAdapter(), StooqAdapter())}


class DataService:
    """Jedyny punkt dostepu do swiec: cache + lancuch zrodel zapasowych."""

    def __init__(self, adapters: dict[str, MarketDataAdapter], store: CandleStore):
        self.adapters = adapters
        self.store = store

    def candidates(self, inst: Instrument, interval: str) -> list[tuple[MarketDataAdapter, str]]:
        out = []
        for name in SOURCE_PRIORITY:
            adapter = self.adapters.get(name)
            if adapter and name in inst.sources and interval in adapter.intervals:
                out.append((adapter, inst.sources[name]))
        return out

    def update(self, inst: Instrument, interval: str) -> tuple[pd.DataFrame, str]:
        """Pobiera brakujace swiece i zwraca (pelna historia, nazwa uzytego zrodla)."""
        if interval not in INTERVALS:
            raise ValueError(f"interwal {interval} nieobslugiwany, dostepne: {INTERVALS}")
        cands = self.candidates(inst, interval)
        if not cands:
            raise DataSourceError(f"{inst.symbol}: brak zrodla dla interwalu {interval}")
        cached = self.store.load(inst.symbol, interval)
        cached_source = self.store.source_of(inst.symbol, interval)
        errors = []
        for adapter, src_symbol in cands:
            # Rozne zrodla notuja rozne instrumenty bazowe (futures vs indeks kasowy),
            # wiec nie sklejamy ich w jedna serie: przy zmianie zrodla pobieramy calosc od nowa.
            same = cached is not None and cached_source in (None, adapter.name)
            # Cofamy sie o kilka dni, zeby nadpisac ostatnia, niedomknieta swiece.
            start = (cached.index[-1] - timedelta(days=5)).to_pydatetime() if same else None
            try:
                fresh = adapter.fetch(src_symbol, interval, start)
            except DataSourceError as exc:
                log.warning("%s: zrodlo %s zawiodlo: %s", inst.symbol, adapter.name, exc)
                errors.append(str(exc))
                continue
            if same:
                df = self.store.merge(inst.symbol, interval, fresh)
            else:
                self.store.save(inst.symbol, interval, fresh)
                df = fresh
            self.store.set_source(inst.symbol, interval, adapter.name)
            return df, adapter.name
        raise DataSourceError(f"{inst.symbol}: wszystkie zrodla zawiodly: {errors}")

    def get(self, inst: Instrument, interval: str, refresh: bool = False) -> pd.DataFrame:
        cached = self.store.load(inst.symbol, interval)
        if cached is not None and not refresh:
            return cached
        df, _ = self.update(inst, interval)
        return df
