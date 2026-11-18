"""Hipoteza H8: dryf po reakcji ceny na wyniki kwartalne. Definicja w CLAUDE_CODE/HIPOTEZY.md.

Daty publikacji: SEC EDGAR (formularze 8-K z punktem 2.02). SEC wymaga naglowka User-Agent z kontaktem:
zmienna srodowiskowa SEC_USER_AGENT (tylko w .env, nie w kodzie). Odstep co najmniej 1 s miedzy zapytaniami.
"""
from __future__ import annotations

import math
import os
import time
from dataclasses import dataclass

import httpx
import numpy as np
import pandas as pd

from ..data.base import DataSourceError

DOW30 = ("AAPL", "AMGN", "AMZN", "AXP", "BA", "CAT", "CRM", "CSCO", "CVX", "DIS", "GS", "HD", "HON", "IBM", "JNJ",
         "JPM", "KO", "MCD", "MMM", "MRK", "MSFT", "NKE", "NVDA", "PG", "SHW", "TRV", "UNH", "V", "VZ", "WMT")
DRIFT = 20
COST = 0.003


class Edgar:
    def __init__(self, user_agent: str | None = None, pause: float = 1.0):
        ua = user_agent or os.environ.get("SEC_USER_AGENT")
        if not ua:
            raise DataSourceError("SEC wymaga kontaktu w naglowku: ustaw SEC_USER_AGENT w .env")
        self.client = httpx.Client(headers={"User-Agent": ua}, timeout=30)
        self.pause, self._last = pause, 0.0

    def _get(self, url: str) -> dict:
        wait = self._last + self.pause - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        self._last = time.monotonic()
        r = self.client.get(url)
        if r.status_code != 200:
            raise DataSourceError(f"SEC {url}: HTTP {r.status_code}")
        return r.json()

    def ciks(self) -> dict[str, int]:
        return {v["ticker"]: int(v["cik_str"]) for v in self._get("https://www.sec.gov/files/company_tickers.json").values()}

    def earnings_times(self, cik: int) -> list[pd.Timestamp]:
        """Czasy przyjecia formularzy 8-K z punktem 2.02 (UTC), z biezacej listy zgloszen (zwykle ~10 lat)."""
        r = self._get(f"https://data.sec.gov/submissions/CIK{cik:010d}.json")["filings"]["recent"]
        return [pd.Timestamp(r["acceptanceDateTime"][i]).tz_convert("UTC") for i, f in enumerate(r["form"])
                if f == "8-K" and "2.02" in (r["items"][i] or "")]


def event_rows(times: list[pd.Timestamp], px: pd.Series, mkt: pd.Series, drift: int = DRIFT) -> list[dict]:
    """Dla kazdej publikacji: reakcja (od sesji przed do drugiej sesji od publikacji) i dryf przez `drift` sesji, oba nad rynkiem."""
    naive = lambda s: s.set_axis(s.index.tz_convert("UTC").tz_localize(None)) if s.index.tz is not None else s
    px, mkt = naive(px.dropna()), naive(mkt.dropna())   # swiece dzienne: data sesji o 00:00
    days = px.index.intersection(mkt.index)
    px, mkt = px.loc[days], mkt.loc[days]
    out = []
    for t in times:
        et = t.tz_convert("America/New_York")
        d = pd.Timestamp(et.date())
        after_close = (et.hour, et.minute) >= (16, 0)
        i0 = days.searchsorted(d, side="right" if after_close else "left")   # pierwsza sesja odzwierciedlajaca wyniki
        if i0 < 1 or i0 + 1 + drift >= len(days):
            continue
        pre, entry, exit_ = i0 - 1, i0 + 1, i0 + 1 + drift
        reaction = (px.iloc[entry] / px.iloc[pre] - 1) - (mkt.iloc[entry] / mkt.iloc[pre] - 1)
        drift_r = (px.iloc[exit_] / px.iloc[entry] - 1) - (mkt.iloc[exit_] / mkt.iloc[entry] - 1)
        out.append({"date": days[i0], "reaction": float(reaction), "drift": float(drift_r)})
    return out


def welch(a: np.ndarray, b: np.ndarray) -> tuple[float, float]:
    """Roznica srednich a - b i statystyka t Welcha."""
    if len(a) < 2 or len(b) < 2:
        return float("nan"), float("nan")
    diff = a.mean() - b.mean()
    se = math.sqrt(a.var(ddof=1) / len(a) + b.var(ddof=1) / len(b))
    return float(diff), float(diff / se) if se > 0 else float("nan")


@dataclass
class Part:
    n_pos: int
    n_neg: int
    diff: float
    t: float
    pos_mean: float


def evaluate(events: pd.DataFrame, share: float = 0.6) -> dict[str, Part]:
    ev = events.sort_values("date").reset_index(drop=True)
    cut = int(len(ev) * share)
    out = {}
    for name, part in (("odkrywcza", ev.iloc[:cut]), ("potwierdzajaca", ev.iloc[cut:])):
        pos = part.loc[part["reaction"] > 0, "drift"].to_numpy()
        neg = part.loc[part["reaction"] < 0, "drift"].to_numpy()
        diff, t = welch(pos, neg)
        out[name] = Part(len(pos), len(neg), diff, t, float(pos.mean()) if len(pos) else float("nan"))
    out["granica"] = ev["date"].iloc[cut] if len(ev) > cut else None
    return out


def verdict(res: dict) -> tuple[bool, str]:
    d, c = res["odkrywcza"], res["potwierdzajaca"]
    ok_d = d.diff > 0 and d.t >= 2
    ok_c = c.diff > 0 and c.t >= 1.65 and c.pos_mean > COST
    if not ok_d:
        return False, "odrzucona na probie odkrywczej"
    if not ok_c:
        return False, "nie utrzymala sie na probie potwierdzajacej"
    return True, "przeszla historie"
