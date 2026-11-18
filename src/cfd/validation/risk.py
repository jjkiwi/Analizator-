"""Hipotezy H11 (kupno po skoku VIX) i H12 (regula 200 sesji dla spolek)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from cfd.validation.calendar_vol import SHARE, _max_dd, _sharpe, sharpe_diff_bootstrap, t_stat


def vix_signal(vix: pd.Series, window: int = 252, q: float = 0.9) -> pd.Series:
    """True, gdy zamkniecie VIX > q-percentyl zamkniec z POPRZEDNICH `window` sesji (przyczynowo)."""
    thr = vix.shift(1).rolling(window, min_periods=window).quantile(q)
    return (vix > thr) & thr.notna()


def vix_episodes(vix: pd.Series, spx: pd.Series, hold: int = 20) -> pd.DataFrame:
    """Epizody bez nakladania: sygnal w dniu t, wejscie na zamknieciu t+1, wyjscie na t+1+hold."""
    df = pd.concat({"vix": vix, "spx": spx}, axis=1).dropna()
    sig = vix_signal(df["vix"]).to_numpy()
    px = df["spx"].to_numpy()
    idx = df.index
    rows, i = [], 0
    while i < len(df):
        if sig[i] and i + 1 + hold < len(df):
            e, x = i + 1, i + 1 + hold
            rows.append({"signal": idx[i], "entry": idx[e], "ret": px[x] / px[e] - 1})
            i = x  # kolejne sygnaly dopiero po wyjsciu
        else:
            i += 1
    return pd.DataFrame(rows)


def h11_report(vix: pd.Series, spx: pd.Series, hold: int = 20) -> dict:
    """Podzial epizodow 60/40, nadwyzka nad srednia 20-sesyjna stopa wszystkich dni."""
    ep = vix_episodes(vix, spx, hold)
    s = spx.dropna()
    fwd = (s.shift(-hold) / s - 1).dropna()
    cut = int(len(ep) * SHARE)
    out = {"n": len(ep)}
    for name, part in (("discovery", ep.iloc[:cut]), ("confirmation", ep.iloc[cut:])):
        lo, hi = part["entry"].min(), part["entry"].max()
        base = fwd[(fwd.index >= lo) & (fwd.index <= hi)].mean()
        ex = part["ret"] - base
        out[name] = {"n": len(part), "od": str(lo.date()), "do": str(hi.date()),
                     "mean_ret": float(part["ret"].mean()), "base": float(base),
                     "excess": float(ex.mean()), "t": t_stat(ex)}
    d, c = out["discovery"], out["confirmation"]
    out["pass"] = bool(d["excess"] > 0 and d["t"] >= 2 and c["excess"] > 0 and c["t"] >= 1.65
                       and c["mean_ret"] > 0.005)
    return out


def sma_rule(closes: pd.DataFrame, n: int = 200, cost: float = 0.001) -> pd.DataFrame:
    """Dzienne stopy portfela rownych wag: regula (close > SMA200, zmiana na nastepnym zamknieciu) i baza."""
    r = closes.pct_change()
    r = r.where(r.abs() <= 0.5)
    pos = (closes > closes.rolling(n, min_periods=n).mean()).astype(float)
    pos = pos.where(closes.rolling(n, min_periods=n).mean().notna())
    held = pos.shift(1)  # decyzja na zamknieciu t, stopa od t do t+1
    trade = held.diff().abs().fillna(0)
    valid = held.notna() & r.notna()
    rule = (held * r - trade * cost).where(valid)
    base = r.where(valid)
    df = pd.DataFrame({"managed": rule.mean(axis=1), "base": base.mean(axis=1)}).dropna()
    return df


def h12_report(closes: pd.DataFrame) -> dict:
    df = sma_rule(closes)
    cut = int(len(df) * SHARE)
    out = {"dni": len(df)}
    ok = True
    for name, part in (("discovery", df.iloc[:cut]), ("confirmation", df.iloc[cut:])):
        sm, sb = _sharpe(part["managed"]), _sharpe(part["base"])
        dm, db = _max_dd(part["managed"]), _max_dd(part["base"])
        out[name] = {"od": str(part.index[0].date()), "do": str(part.index[-1].date()),
                     "sharpe_rule": sm, "sharpe_base": sb, "dd_rule": dm, "dd_base": db,
                     "cagr_rule": float((1 + part["managed"]).prod() ** (252 / len(part)) - 1),
                     "cagr_base": float((1 + part["base"]).prod() ** (252 / len(part)) - 1)}
        ok &= sm - sb >= 0.10 and dm > db
    out["p_bootstrap"] = sharpe_diff_bootstrap(df)
    out["pass"] = bool(ok and out["p_bootstrap"] < 0.10)
    return out
