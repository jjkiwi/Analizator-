"""Testy na horyzoncie miesiecznym: trend (H3) i sila wzgledna (H4). Definicje w CLAUDE_CODE/HIPOTEZY.md.

Wszystko liczone na zamknieciach miesiaca: sygnal z konca miesiaca t, wynik z miesiaca t+1 (bez zagladania w przyszlosc).
Koszty: pelny spread od kazdej zmiany wagi (ostroznie: w obie strony liczony caly spread), bez swapu, czyli jak dla
akcji i ETF-ow trzymanych bez dzwigni.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd

UNIVERSE = ("indices", "stocks", "metals", "crypto")   # surowce wylaczone: kontrakty ciagle bez korekty rolowania
EXCLUDED = ("VIX",)                                     # indeks zmiennosci nie jest instrumentem do trzymania
TREND_WINDOWS = (3, 6, 12)
RANK_WINDOW = 6
TOP_SHARE = 1 / 3
DISCOVERY_SHARE = 0.6


def monthly_closes(daily: dict[str, pd.Series], now: pd.Timestamp | None = None) -> pd.DataFrame:
    """Zamkniecia na koniec pelnych miesiecy (biezacy, niedomkniety miesiac jest odrzucany)."""
    now = now or pd.Timestamp.now(tz="UTC")
    cols = {}
    for sym, s in daily.items():
        s = s.dropna()
        if s.empty:
            continue
        m = s.groupby(s.index.tz_convert("UTC").tz_localize(None).to_period("M")).last()
        cols[sym] = m[m.index < now.tz_localize(None).to_period("M")]
    return pd.DataFrame(cols).sort_index()


def trend_signal(prices: pd.DataFrame) -> pd.DataFrame:
    """True, gdy co najmniej dwie z trzech stop zwrotu (3, 6, 12 miesiecy) sa dodatnie. NaN bez 12 miesiecy historii."""
    votes = sum((prices / prices.shift(w) - 1 > 0).astype(float) for w in TREND_WINDOWS)
    return (votes >= 2).where(prices.shift(max(TREND_WINDOWS)).notna())


@dataclass
class Series:
    name: str
    returns: pd.Series   # miesieczne stopy (albo roznice stop) po kosztach

    def stats(self) -> dict:
        r = self.returns.dropna()
        n = len(r)
        if n < 3:
            return {"n": n, "mean": float("nan"), "t": float("nan"), "sharpe": float("nan")}
        sd = r.std(ddof=1)
        return {"n": n, "mean": float(r.mean()), "t": float(r.mean() / (sd / math.sqrt(n))) if sd > 0 else 0.0,
                "sharpe": float(r.mean() / sd * math.sqrt(12)) if sd > 0 else 0.0}


def _costs(weights: pd.DataFrame, spread: pd.Series) -> pd.Series:
    """Koszt zmiany skladu: |zmiana wagi| x spread instrumentu, przypisany do miesiaca, w ktorym waga obowiazuje."""
    turn = weights.fillna(0).diff().abs()
    turn.iloc[0] = weights.iloc[0].fillna(0).abs()
    return (turn * spread.reindex(weights.columns).fillna(0)).sum(axis=1)


def run(prices: pd.DataFrame, spread: pd.Series) -> dict[str, pd.Series]:
    """Zwraca miesieczne serie: trend (H3), kup_i_trzymaj, sila_roznica (H4: gorna 1/3 minus srednia zakresu)."""
    nxt = prices.shift(-1) / prices - 1                      # stopa z miesiaca t+1, przypisana do konca miesiaca t
    sig = trend_signal(prices)
    live = sig.notna() & nxt.notna()                         # zakres w danym miesiacu
    n = live.sum(axis=1)
    w_trend = (sig.where(live) == True).astype(float).div(n.where(n > 0), axis=0)   # noqa: E712
    w_hold = live.astype(float).div(n.where(n > 0), axis=0)
    trend = (w_trend * nxt).sum(axis=1) - _costs(w_trend, spread)
    hold = (w_hold * nxt).sum(axis=1)

    mom = (prices / prices.shift(RANK_WINDOW) - 1).where(live)
    k = np.ceil(n * TOP_SHARE)
    top = mom.rank(axis=1, ascending=False, method="first").le(k, axis=0) & live
    w_top = top.astype(float).div(top.sum(axis=1).where(top.sum(axis=1) > 0), axis=0)
    diff = (w_top * nxt).sum(axis=1) - _costs(w_top, spread) - hold
    ok = n >= 6                                              # ranking ma sens dopiero przy kilku instrumentach
    idx = [p + 1 for p in prices.index]                      # etykieta: miesiac, w ktorym wynik powstal
    out = {"trend": trend.where(n > 0), "kup_i_trzymaj": hold.where(n > 0), "sila_roznica": diff.where(ok),
           "udzial_w_trendzie": (w_trend.sum(axis=1)).where(n > 0), "liczba_instrumentow": n.astype(float)}
    return {k_: v.set_axis(idx).iloc[:-1] for k_, v in out.items()}   # ostatni wiersz nie ma jeszcze wyniku t+1


def split(r: pd.Series) -> tuple[pd.Series, pd.Series]:
    r = r.dropna()
    cut = int(len(r) * DISCOVERY_SHARE)
    return r.iloc[:cut], r.iloc[cut:]


def summarize(series: dict[str, pd.Series]) -> list[dict]:
    rows = []
    for name in ("trend", "kup_i_trzymaj", "sila_roznica"):
        d, c = split(series[name])
        rows.append({"name": name, "od": str(series[name].dropna().index.min()), "granica": str(c.index.min()) if len(c) else None,
                     "discovery": Series(name, d).stats(), "confirmation": Series(name, c).stats()})
    return rows


def current_state(prices: pd.DataFrame) -> dict:
    """Stan reguly trendu miesiecznego na koniec ostatniego pelnego miesiaca: per instrument stopy 3/6/12 mies. i werdykt."""
    if prices.empty:
        return {"month": None, "rows": []}
    sig = trend_signal(prices).iloc[-1]
    rows = []
    for sym in prices.columns:
        if pd.isna(sig[sym]) or pd.isna(prices[sym].iloc[-1]):
            continue
        rets = {w: float(prices[sym].iloc[-1] / prices[sym].iloc[-1 - w] - 1) for w in TREND_WINDOWS}
        rows.append({"symbol": sym, "in_trend": bool(sig[sym]), "returns": rets})
    return {"month": str(prices.index[-1]), "rows": rows}
