"""Hipotezy H9 (zarzadzanie zmiennoscia) i H10 (przelom miesiaca) na koszyku indeksow. Definicje: CLAUDE_CODE/HIPOTEZY.md."""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

EXCLUDED = ("VIX", "USDIDX")
SHARE = 0.6


def daily_returns(closes: dict[str, pd.Series]) -> pd.DataFrame:
    cols = {}
    for sym, c in closes.items():
        c = c.dropna()
        idx = c.index.tz_convert("UTC").tz_localize(None) if c.index.tz is not None else c.index
        c = c.set_axis(idx)
        r = c.pct_change()
        r = r[(r.abs() < 0.25) & (c.shift(1) > 0)]       # odrzuc bledy danych (skoki > 25% dziennie na indeksie)
        cols[sym] = r
    return pd.DataFrame(cols).sort_index()


def _sharpe(r: pd.Series) -> float:
    r = r.dropna()
    sd = r.std(ddof=1)
    return float(r.mean() / sd * math.sqrt(252)) if sd > 0 else float("nan")


def _max_dd(r: pd.Series) -> float:
    eq = (1 + r.dropna()).cumprod()
    return float((eq / eq.cummax() - 1).min())


def vol_managed(rets: pd.DataFrame, spread: float = 0.0003) -> pd.DataFrame:
    """Koszyk o stalej ekspozycji i koszyk zarzadzany zmiennoscia (ekspozycja zmieniana na koniec miesiaca, przyczynowo)."""
    basket = rets.mean(axis=1, skipna=True).dropna()
    vol21 = basket.rolling(21).std() * math.sqrt(252)
    target = vol21.expanding(min_periods=252).mean()
    month = basket.index.to_period("M")
    month_end = basket.groupby(month).apply(lambda x: x.index[-1])
    w_at_end = (target / vol21).clip(upper=1.0).loc[month_end.values]           # znane na zamknieciu ostatniej sesji
    w = pd.Series(np.nan, index=basket.index)
    w.loc[month_end.values] = w_at_end.values
    w = w.shift(1).ffill()                                                      # obowiazuje od nastepnej sesji
    managed = w * basket - w.diff().abs().fillna(0) * spread
    df = pd.DataFrame({"base": basket, "managed": managed, "w": w}).dropna()
    return df


def h9_report(df: pd.DataFrame) -> dict:
    cut = df.index[int(len(df) * SHARE)]
    out = {"granica": cut, "od": df.index[0], "srednia_ekspozycja": float(df["w"].mean())}
    for name, part in (("odkrywcza", df[df.index < cut]), ("potwierdzajaca", df[df.index >= cut])):
        out[name] = {k: {"sharpe": _sharpe(part[k]), "max_dd": _max_dd(part[k]), "roczna": float(part[k].mean() * 252)} for k in ("base", "managed")}
    return out


def sharpe_diff_bootstrap(df: pd.DataFrame, n: int = 2000, block: int = 21, seed: int = 0) -> float:
    """Jednostronne p: odsetek prob bootstrapu blokowego, w ktorych Sharpe zarzadzanego <= Sharpe bazowego."""
    rng = np.random.default_rng(seed)
    a, b = df["managed"].to_numpy(), df["base"].to_numpy()
    m = len(a)
    starts_n = m - block
    worse = 0
    for _ in range(n):
        st = rng.integers(0, starts_n, size=m // block + 1)
        idx = (st[:, None] + np.arange(block)[None, :]).ravel()[:m]
        sa, sb = a[idx], b[idx]
        if sa.mean() / sa.std() <= sb.mean() / sb.std():
            worse += 1
    return worse / n


def turn_of_month(rets: pd.DataFrame) -> pd.DataFrame:
    """Na miesiac: suma 4 sesji przelomu (ostatnia + 3 pierwsze nastepnego) minus 4 x srednia pozostalych sesji; srednia po indeksach."""
    rows = {}
    for sym in rets.columns:
        r = rets[sym].dropna()
        if len(r) < 300:
            continue
        per = r.index.to_period("M")
        months = sorted(set(per))
        by = {m: r[per == m] for m in months}
        for i in range(1, len(months) - 1):
            prev, cur = by[months[i - 1]], by[months[i]]
            if len(prev) < 10 or len(cur) < 10:
                continue
            tom = pd.concat([prev.iloc[-1:], cur.iloc[:3]])
            other = cur.iloc[3:-1]                                   # pozostale sesje miesiaca (bez ostatniej, ona nalezy do nastepnego przelomu)
            rows.setdefault(months[i], []).append((float(tom.sum()), float(tom.sum() - 4 * other.mean())))
    out = pd.DataFrame({"tom": {m: np.mean([x[0] for x in v]) for m, v in rows.items()},
                        "excess": {m: np.mean([x[1] for x in v]) for m, v in rows.items()},
                        "n_idx": {m: len(v) for m, v in rows.items()}}).sort_index()
    return out


def t_stat(x: pd.Series) -> float:
    x = x.dropna()
    sd = x.std(ddof=1)
    return float(x.mean() / (sd / math.sqrt(len(x)))) if len(x) > 1 and sd > 0 else float("nan")
