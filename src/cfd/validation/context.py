"""Test filtra kontekstowego: czy sygnaly strategii trafiaja czesciej w sprzyjajacym kontekscie.

Metoda (wszystko przyczynowo, bez zagladania w przyszlosc):
1. Transakcje pochodza wylacznie z okien testowych walk-forward (parametry dobrane na danych wczesniejszych).
2. Kazda transakcja dostaje etykiety kontekstu znane PRZED wejsciem (ostatnia zamknieta swieca, poprzednia sesja
   dzienna, serie fundamentalne z opoznieniem publikacji).
3. Transakcje dzielone sa w czasie: starsze 60% to proba odkrywcza, nowsze 40% to proba potwierdzajaca.
   Filtr jest "kandydatem", gdy na probie odkrywczej daje dodatni wynik istotnie powyzej zera, a "potwierdzony",
   gdy utrzymuje to na probie potwierdzajacej, ktorej przy wyborze nie widzial.

Hipotez jest kilkaset, wiec czesc kandydatow pojawi sie przez przypadek: liczy sie tylko proba potwierdzajaca.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import timedelta

import numpy as np
import pandas as pd

from ..features.indicators import atr, regime, sma
from ..fundamentals.bias import compute_bias
from ..strategies import PARAM_GRIDS, REGISTRY
from .walkforward import walk_forward

FEATURES = ("regime", "d1_trend", "vol", "session", "vix", "bias")
PUBLICATION_LAG_DAYS = 7  # serie fundamentalne (FRED, EIA, COT) uznajemy za znane dopiero po tygodniu
DISCOVERY_SHARE = 0.6
MIN_N_DISCOVERY, MIN_N_CONFIRM = 200, 100
T_DISCOVERY, T_CONFIRM = 2.0, 1.65


def _last_before(series: pd.Series, times: pd.DatetimeIndex) -> np.ndarray:
    """Wartosc serii z ostatniego wiersza o indeksie scisle wczesniejszym niz dany czas."""
    pos = series.index.searchsorted(times, side="left") - 1
    vals = series.to_numpy(dtype=object)
    return np.array([vals[p] if p >= 0 else None for p in pos], dtype=object)


def _session(hour: int) -> str:
    return "europa" if 7 <= hour < 13 else "usa" if 13 <= hour < 21 else "azja"


def label_trades(trades: pd.DataFrame, df: pd.DataFrame, daily: pd.DataFrame, interval: str,
                 vix: pd.Series | None = None, bias: pd.Series | None = None) -> pd.DataFrame:
    """Dodaje kolumny kontekstu do transakcji jednego instrumentu. `trades`: entry_time, side, r."""
    out = trades.copy()
    t = pd.DatetimeIndex(out["entry_time"])
    side = out["side"].to_numpy()

    reg = _last_before(regime(df), t)
    out["regime"] = [
        "brak" if r in (None, "unknown") else "konsolidacja" if r == "range" else "mieszany" if r == "mixed"
        else "z_trendem" if (r == "trend_up") == (s > 0) else "pod_trend"
        for r, s in zip(reg, side)
    ]

    # trend dzienny z POPRZEDNIEJ sesji: swieca dzienna z dnia wejscia nie jest jeszcze zamknieta
    d_up = (daily["close"] > sma(daily["close"], 200)).where(sma(daily["close"], 200).notna())
    d_vals = _last_before(d_up, t.normalize())
    out["d1_trend"] = ["brak" if v is None or pd.isna(v) else "zgodny" if bool(v) == (s > 0) else "przeciwny" for v, s in zip(d_vals, side)]

    rel = (atr(df) / df["close"])
    pct = rel.rolling(250, min_periods=100).rank(pct=True)
    p_vals = _last_before(pct, t)
    out["vol"] = ["brak" if v is None or pd.isna(v) else "wysoka" if v > 2 / 3 else "niska" if v < 1 / 3 else "srednia" for v in p_vals]

    out["session"] = [_session(h) for h in t.hour] if interval in ("30m", "1h", "4h") else "dzienny"

    if vix is not None and len(vix):
        high = (vix > vix.rolling(250, min_periods=100).median()).where(vix.rolling(250, min_periods=100).median().notna())
        v_vals = _last_before(high, t.normalize())
        out["vix"] = ["brak" if v is None or pd.isna(v) else "wysoki" if v else "niski" for v in v_vals]
    else:
        out["vix"] = "brak"

    if bias is not None and len(bias):
        b_vals = _last_before(bias, t)
        out["bias"] = [
            "brak" if b is None or pd.isna(b) else "zgodny" if b * s >= 0.5 else "przeciwny" if b * s <= -0.5 else "neutralny"
            for b, s in zip(b_vals, side)
        ]
    else:
        out["bias"] = "brak"
    return out


def bias_history(components: list[dict], get_series, start: pd.Timestamp, end: pd.Timestamp) -> pd.Series:
    """Bias fundamentalny liczony co tydzien tak, jak bylby znany danego dnia (serie uciete o opoznienie publikacji)."""
    cache: dict[str, pd.Series] = {}

    def series_until(cut: pd.Timestamp):
        def get(series_id: str) -> pd.Series:
            if series_id not in cache:
                s = get_series(series_id).dropna().sort_index()
                idx = pd.DatetimeIndex(s.index)
                cache[series_id] = s.set_axis(idx.tz_localize("UTC") if idx.tz is None else idx.tz_convert("UTC"))
            s = cache[series_id]
            return s[s.index <= cut]
        return get

    out = {}
    for day in pd.date_range(start.normalize(), end.normalize(), freq="7D", tz="UTC"):
        cut = day - timedelta(days=PUBLICATION_LAG_DAYS)
        value, _ = compute_bias(components, series_until(cut), now=cut.to_pydatetime())
        if value is not None:
            out[day] = value
    return pd.Series(out, dtype=float)


def collect_trades(instruments, data_service, interval: str, strategies: list[str], train_bars: int = 750,
                   test_bars: int = 250, vix: pd.Series | None = None, bias_for=None, progress=None) -> pd.DataFrame:
    """Transakcje z okien testowych walk-forward dla wszystkich instrumentow, z etykietami kontekstu."""
    from ..data.quality import roll_mask

    frames = []
    for inst in instruments:
        try:
            df = data_service.get(inst, interval)
            daily = df if interval == "1d" else data_service.get(inst, "1d")
        except Exception:
            continue
        roll = roll_mask(inst, df)
        bias = None
        for name in strategies:
            res = walk_forward(df, REGISTRY[name], PARAM_GRIDS.get(name, {}), inst.costs, train_bars, test_bars, roll=roll)
            if not res.trades:
                continue
            tr = pd.DataFrame({
                "entry_time": pd.DatetimeIndex([x.entry_time for x in res.trades]).tz_convert("UTC"),
                "side": [x.side for x in res.trades],
                "r": [x.r_multiple for x in res.trades],
                "cost_r": [x.cost_r for x in res.trades],
            })
            if bias is None and bias_for is not None:
                bias = bias_for(inst, tr["entry_time"].min(), tr["entry_time"].max())
            tr = label_trades(tr, df, daily, interval, vix, bias)
            tr.insert(0, "strategy", name)
            tr.insert(0, "interval", interval)
            tr.insert(0, "category", inst.category)
            tr.insert(0, "symbol", inst.symbol)
            frames.append(tr)
        if progress:
            progress(inst.symbol)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


@dataclass
class Cell:
    interval: str
    strategy: str
    scope: str      # "wszystkie" albo kategoria instrumentow
    feature: str
    value: str
    n_d: int
    mean_d: float
    t_d: float
    n_c: int
    mean_c: float
    t_c: float

    @property
    def candidate(self) -> bool:
        return self.n_d >= MIN_N_DISCOVERY and self.mean_d > 0 and self.t_d >= T_DISCOVERY

    @property
    def confirmed(self) -> bool:
        return self.candidate and self.n_c >= MIN_N_CONFIRM and self.mean_c > 0 and self.t_c >= T_CONFIRM


def _stats(r: pd.Series) -> tuple[int, float, float]:
    n = len(r)
    if n < 2:
        return n, float(r.mean()) if n else 0.0, 0.0
    sd = r.std(ddof=1)
    return n, float(r.mean()), float(r.mean() / (sd / math.sqrt(n))) if sd > 0 else 0.0


def evaluate(trades: pd.DataFrame, features: tuple[str, ...] = FEATURES) -> tuple[list[Cell], dict]:
    """Ocena filtrow: podzial w czasie na probe odkrywcza i potwierdzajaca, osobno dla kazdego interwalu."""
    cells: list[Cell] = []
    baseline: dict = {}
    for interval, part in trades.groupby("interval"):
        cutoff = part["entry_time"].quantile(DISCOVERY_SHARE)
        disc, conf = part[part["entry_time"] < cutoff], part[part["entry_time"] >= cutoff]
        for strategy in sorted(part["strategy"].unique()):
            d_s, c_s = disc[disc["strategy"] == strategy], conf[conf["strategy"] == strategy]
            baseline[(interval, strategy)] = {"cutoff": cutoff, "discovery": _stats(d_s["r"]), "confirmation": _stats(c_s["r"])}
            scopes = [("wszystkie", d_s, c_s)] + [
                (cat, d_s[d_s["category"] == cat], c_s[c_s["category"] == cat]) for cat in sorted(part["category"].unique())
            ]
            for scope, d, c in scopes:
                for feat in features:
                    for value in sorted(set(d[feat]) | set(c[feat])):
                        if value in ("brak", "dzienny"):
                            continue
                        nd, md, td = _stats(d.loc[d[feat] == value, "r"])
                        nc, mc, tc = _stats(c.loc[c[feat] == value, "r"])
                        cells.append(Cell(interval, strategy, scope, feat, value, nd, md, td, nc, mc, tc))
    return cells, baseline


def render_markdown(cells: list[Cell], baseline: dict) -> str:
    lines = ["### Punkt odniesienia (wszystkie sygnaly, bez filtra)", "",
             "| Interwał | Strategia | Odkrywcza: n | Odkrywcza: śr. R | Potwierdzająca: n | Potwierdzająca: śr. R | Granica prób |",
             "|---|---|---|---|---|---|---|"]
    for (interval, strategy), b in sorted(baseline.items()):
        (nd, md, _), (nc, mc, _) = b["discovery"], b["confirmation"]
        lines.append(f"| {interval} | {strategy} | {nd} | {md:+.3f} | {nc} | {mc:+.3f} | {b['cutoff']:%Y-%m-%d} |")
    tested = [c for c in cells if c.n_d >= MIN_N_DISCOVERY]
    cand = [c for c in cells if c.candidate]
    conf = [c for c in cells if c.confirmed]
    by_chance = len(tested) * 0.025  # jednostronnie t >= 2 to ok. 2,5% przy braku efektu
    lines += ["", f"Filtrów z wystarczającą próbą: {len(tested)}. Kandydatów na próbie odkrywczej: {len(cand)} "
                  f"(z samego przypadku spodziewane ok. {by_chance:.0f}). Potwierdzonych na próbie niewidzianej: {len(conf)} "
                  f"(z samego przypadku spodziewane ok. {len(cand) * 0.05:.1f}).", "",
              "### Kandydaci i ich wynik na próbie potwierdzającej", "",
              "| Int. | Strategia | Zakres | Cecha = wartość | Odkr.: n | Odkr.: śr. R | Odkr.: t | Potw.: n | Potw.: śr. R | Potw.: t | Wynik |",
              "|---|---|---|---|---|---|---|---|---|---|---|"]
    for c in sorted(cand, key=lambda c: (not c.confirmed, -c.t_c)):
        verdict = "POTWIERDZONY" if c.confirmed else "za mała próba" if c.n_c < MIN_N_CONFIRM else "nie utrzymał się"
        lines.append(f"| {c.interval} | {c.strategy} | {c.scope} | {c.feature} = {c.value} | {c.n_d} | {c.mean_d:+.3f} | {c.t_d:.1f} "
                     f"| {c.n_c} | {c.mean_c:+.3f} | {c.t_c:.1f} | {verdict} |")
    if not cand:
        lines.append("| – | – | – | brak kandydatów | | | | | | | |")
    return "\n".join(lines)
