from __future__ import annotations

from pathlib import Path

import pandas as pd


class CandleStore:
    """Cache swiec w Parquet: data/candles/<interwal>/<symbol>.parquet"""

    def __init__(self, root: Path | str = "data/candles"):
        self.root = Path(root)

    def _path(self, symbol: str, interval: str) -> Path:
        safe = symbol.replace("/", "_")
        return self.root / interval / f"{safe}.parquet"

    def load(self, symbol: str, interval: str) -> pd.DataFrame | None:
        path = self._path(symbol, interval)
        if not path.exists():
            return None
        return pd.read_parquet(path)

    def save(self, symbol: str, interval: str, df: pd.DataFrame) -> None:
        path = self._path(symbol, interval)
        path.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(path)

    def source_of(self, symbol: str, interval: str) -> str | None:
        meta = self._path(symbol, interval).with_suffix(".source")
        return meta.read_text().strip() if meta.exists() else None

    def set_source(self, symbol: str, interval: str, source: str) -> None:
        meta = self._path(symbol, interval).with_suffix(".source")
        meta.parent.mkdir(parents=True, exist_ok=True)
        meta.write_text(source)

    def merge(self, symbol: str, interval: str, new: pd.DataFrame) -> pd.DataFrame:
        """Dokleja nowe swiece do cache; przy konflikcie wygrywa swiezsza wersja."""
        old = self.load(symbol, interval)
        df = new if old is None else pd.concat([old, new])
        df = df[~df.index.duplicated(keep="last")].sort_index()
        self.save(symbol, interval, df)
        return df
