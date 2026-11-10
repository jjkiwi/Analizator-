"""Wskazniki liczone wylacznie na danych z przeszlosci (bez zagladania w przyszlosc)."""
from __future__ import annotations

import numpy as np
import pandas as pd


def sma(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(period, min_periods=period).mean()


def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False, min_periods=period).mean()


def _wilder(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = _wilder(delta.clip(lower=0), period)
    loss = _wilder(-delta.clip(upper=0), period)
    out = 100 - 100 / (1 + gain / loss)
    return out.where(loss != 0, 100.0).where(gain.notna())


def true_range(df: pd.DataFrame) -> pd.Series:
    prev_close = df["close"].shift(1)
    return pd.concat(
        [df["high"] - df["low"], (df["high"] - prev_close).abs(), (df["low"] - prev_close).abs()],
        axis=1,
    ).max(axis=1)


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    return _wilder(true_range(df), period)


def adx(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Sila trendu (0-100). Ponizej ~20 rynek zwykle jest w konsolidacji."""
    up = df["high"].diff()
    down = -df["low"].diff()
    plus_dm = pd.Series(np.where((up > down) & (up > 0), up, 0.0), index=df.index)
    minus_dm = pd.Series(np.where((down > up) & (down > 0), down, 0.0), index=df.index)
    tr = _wilder(true_range(df), period)
    plus_di = 100 * _wilder(plus_dm, period) / tr
    minus_di = 100 * _wilder(minus_dm, period) / tr
    denom = (plus_di + minus_di).replace(0, np.nan)
    dx = 100 * (plus_di - minus_di).abs() / denom
    return _wilder(dx.fillna(0.0).where(tr.notna()), period)


def bollinger(close: pd.Series, period: int = 20, k: float = 2.0) -> pd.DataFrame:
    mid = sma(close, period)
    sd = close.rolling(period, min_periods=period).std(ddof=0)
    return pd.DataFrame({"mid": mid, "upper": mid + k * sd, "lower": mid - k * sd})


def donchian(df: pd.DataFrame, period: int = 20) -> pd.DataFrame:
    """Kanal z N POPRZEDNICH swiec (biezaca swieca nie wchodzi do kanalu)."""
    return pd.DataFrame(
        {
            "upper": df["high"].rolling(period, min_periods=period).max().shift(1),
            "lower": df["low"].rolling(period, min_periods=period).min().shift(1),
        }
    )


def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    line = ema(close, fast) - ema(close, slow)
    sig = line.ewm(span=signal, adjust=False, min_periods=signal).mean()
    return pd.DataFrame({"macd": line, "signal": sig, "hist": line - sig})


def regime(df: pd.DataFrame, adx_period: int = 14, trend_level: float = 25.0, range_level: float = 20.0) -> pd.Series:
    """Rezim rynku: 'trend_up', 'trend_down', 'range' albo 'mixed'."""
    a = adx(df, adx_period)
    e50, e200 = ema(df["close"], 50), ema(df["close"], 200)
    out = pd.Series("mixed", index=df.index, dtype=object)
    out[(a >= trend_level) & (e50 > e200)] = "trend_up"
    out[(a >= trend_level) & (e50 < e200)] = "trend_down"
    out[a < range_level] = "range"
    out[a.isna() | e200.isna()] = "unknown"
    return out
