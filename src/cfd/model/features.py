"""Cechy modelu przewidywan (H5) liczone przyczynowo na zamknieciu dnia t i cel: kierunek z t+1..t+h.

Definicje ustalone przed testem w CLAUDE_CODE/HIPOTEZY.md (H5). Kazda cecha w wierszu t korzysta tylko ze swiec do t
wlacznie; indeks szerokiego rynku (US500) jest brany z poprzedniego dnia kalendarzowego, bo rozne gieldy zamykaja sie
o roznych godzinach (zamkniecie US500 z dnia t moze byc pozniejsze niz zamkniecie np. indeksu azjatyckiego z dnia t).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..features.indicators import adx, atr, rsi, sma

HORIZONS = (5, 20)
CATEGORIES = ("indices", "stocks", "metals", "crypto")
MARKET = "US500"
RET_WINDOWS = (5, 20, 60, 120, 250)
TREND_SESSIONS = {3: 63, 6: 126, 12: 252}          # miesiace -> sesje (jak glosy trendu w H3)
NUMERIC = (
    [f"ret_{w}" for w in RET_WINDOWS]
    + ["vol_20", "vol_60", "dist_sma50_atr", "dist_sma200_atr", "rsi_14", "adx_14"]
    + [f"trend_{m}m" for m in TREND_SESSIONS]
    + ["rel_mkt_20", "rel_mkt_60", "range_pos_252"]
)
FEATURES = NUMERIC + [f"cat_{c}" for c in CATEGORIES]


def _daily_index(df: pd.DataFrame) -> pd.DataFrame:
    """Indeks dzienny w UTC bez godziny, bez duplikatow (ostatnia swieca dnia wygrywa)."""
    df = df.copy()
    idx = pd.DatetimeIndex(df.index)
    idx = idx.tz_convert("UTC") if idx.tz is not None else idx.tz_localize("UTC")
    df.index = idx.normalize()
    return df[~df.index.duplicated(keep="last")].sort_index()


def instrument_features(df: pd.DataFrame, category: str, market_close: pd.Series | None = None) -> pd.DataFrame:
    """Cechy jednego instrumentu na kazdy dzien (wiersz t zna tylko swiece do t)."""
    df = _daily_index(df)
    c = df["close"].astype(float)
    logc = np.log(c)
    r1 = logc.diff()
    out = pd.DataFrame(index=df.index)
    for w in RET_WINDOWS:
        out[f"ret_{w}"] = logc - logc.shift(w)
    out["vol_20"] = r1.rolling(20, min_periods=20).std()
    out["vol_60"] = r1.rolling(60, min_periods=60).std()
    a = atr(df, 14).replace(0, np.nan)
    out["dist_sma50_atr"] = (c - sma(c, 50)) / a
    out["dist_sma200_atr"] = (c - sma(c, 200)) / a
    out["rsi_14"] = rsi(c, 14) / 100.0
    out["adx_14"] = adx(df, 14) / 100.0
    for m, n in TREND_SESSIONS.items():
        out[f"trend_{m}m"] = np.sign(c / c.shift(n) - 1).where(c.shift(n).notna())
    if market_close is not None and len(market_close):
        mk = _daily_index(market_close.to_frame("close"))["close"]
        # rynek znany z poprzedniego dnia kalendarzowego (bez zagladania w zamkniecie pozniejsze niz zamkniecie instrumentu)
        lagged = mk.reindex(mk.index.union(df.index - pd.Timedelta(days=1))).ffill()
        m_t = pd.Series(lagged.reindex(df.index - pd.Timedelta(days=1)).to_numpy(), index=df.index)
        lm = np.log(m_t)
        for w in (20, 60):
            out[f"rel_mkt_{w}"] = out[f"ret_{w}"] - (lm - lm.shift(w))
    else:
        out["rel_mkt_20"] = np.nan
        out["rel_mkt_60"] = np.nan
    lo = df["low"].rolling(252, min_periods=252).min()
    hi = df["high"].rolling(252, min_periods=252).max()
    out["range_pos_252"] = ((c - lo) / (hi - lo).replace(0, np.nan)).clip(0, 1)
    for cat in CATEGORIES:
        out[f"cat_{cat}"] = 1.0 if category == cat else 0.0
    out["close"] = c
    return out


def add_targets(feat: pd.DataFrame, horizons=HORIZONS) -> pd.DataFrame:
    """Cel y_h = 1, gdy zamkniecie w t+h > zamkniecie w t; end_h = data swiecy t+h (do oczyszczania). NaN, gdy brak t+h."""
    feat = feat.copy()
    c = feat["close"]
    dates = pd.Series(feat.index, index=feat.index)
    for h in horizons:
        fut = c.shift(-h)
        feat[f"y_{h}"] = (fut > c).astype(float).where(fut.notna())
        feat[f"end_{h}"] = dates.shift(-h)
    return feat


def build_dataset(frames: dict[str, pd.DataFrame], categories: dict[str, str], horizons=HORIZONS) -> pd.DataFrame:
    """Zbior w ukladzie dlugim: wiersz = (data, symbol). Wiersze bez pelnych cech sa odrzucane; cel moze byc NaN (ostatnie h dni)."""
    market = frames.get(MARKET)
    mclose = market["close"] if market is not None else None
    parts = []
    for sym, df in frames.items():
        if df is None or len(df) < 260:
            continue
        f = add_targets(instrument_features(df, categories[sym], mclose), horizons)
        f = f.dropna(subset=NUMERIC)
        if f.empty:
            continue
        f.insert(0, "symbol", sym)
        f.insert(1, "category", categories[sym])
        parts.append(f.rename_axis("date").reset_index())
    if not parts:
        raise ValueError("Brak instrumentow z wystarczajaca historia (min. 260 swiec) do zbudowania zbioru.")
    return pd.concat(parts, ignore_index=True).sort_values(["date", "symbol"], kind="stable").reset_index(drop=True)


def load_frames(data_dir="data", instruments_path=None, today: pd.Timestamp | None = None) -> tuple[dict, dict]:
    """Swiece dzienne z cache dla zakresu H3. Swieca z dzisiejsza data (niedomknieta) jest odrzucana."""
    from pathlib import Path

    from ..data import CandleStore, DataService, DataSourceError, default_adapters
    from ..instruments import load_instruments
    from ..validation import monthly

    insts = load_instruments(instruments_path) if instruments_path else load_instruments()
    svc = DataService(default_adapters(), CandleStore(Path(data_dir) / "candles"))
    today = (today or pd.Timestamp.now(tz="UTC")).normalize()
    frames, cats = {}, {}
    for inst in insts.values():
        if inst.category not in monthly.UNIVERSE or inst.symbol in monthly.EXCLUDED or not inst.sources:
            continue
        try:
            df = _daily_index(svc.get(inst, "1d"))
        except DataSourceError:
            continue
        frames[inst.symbol] = df[df.index < today]
        cats[inst.symbol] = inst.category
    return frames, cats
