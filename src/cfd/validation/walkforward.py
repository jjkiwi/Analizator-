"""Walk-forward: parametry wybierane na oknie treningowym, oceniane na kolejnym, niewidzianym.

Wynik to wylacznie transakcje z okien testowych, czyli przyblizenie tego,
co strategia zrobilaby "na zywo" przy okresowym strojeniu.
"""
from __future__ import annotations

import itertools
from dataclasses import dataclass, field

import pandas as pd

from ..backtest import run_backtest, summarize
from ..models import Costs, Trade


@dataclass
class WalkForwardResult:
    trades: list[Trade] = field(default_factory=list)
    folds: list[dict] = field(default_factory=list)

    @property
    def stats(self) -> dict:
        return summarize(self.trades)


def _window_trades(df, strategy, costs, start: int, end: int, max_bars) -> list[Trade]:
    """Transakcje otwarte w [start, end). Wskazniki licza sie na calej historii do `end`."""
    hist = df.iloc[:end]
    signals = strategy.generate(hist).copy()
    signals.iloc[:start, signals.columns.get_loc("side")] = 0
    return run_backtest(hist, signals, costs, max_bars=max_bars)


def walk_forward(
    df: pd.DataFrame,
    strategy_cls,
    grid: dict[str, list],
    costs: Costs = Costs(),
    train_bars: int = 750,
    test_bars: int = 250,
    min_train_trades: int = 5,
    max_bars: int | None = None,
) -> WalkForwardResult:
    res = WalkForwardResult()
    combos = [dict(zip(grid, vals)) for vals in itertools.product(*grid.values())] or [{}]
    start = 0
    while start + train_bars + test_bars <= len(df):
        tr_end = start + train_bars
        te_end = tr_end + test_bars
        best, best_score = None, None
        for params in combos:
            st = summarize(_window_trades(df, strategy_cls(**params), costs, start, tr_end, max_bars))
            if st.get("trades", 0) < min_train_trades:
                continue
            if best_score is None or st["expectancy_r"] > best_score:
                best, best_score = params, st["expectancy_r"]
        fold = {"train_start": df.index[start], "test_start": df.index[tr_end], "test_end": df.index[te_end - 1]}
        if best is None or best_score <= 0:
            # Brak dodatniej przewagi na treningu = w tym oknie nie handlujemy.
            fold.update(params=None, train_expectancy_r=best_score, test_trades=0, test_total_r=0.0)
        else:
            trades = _window_trades(df, strategy_cls(**best), costs, tr_end, te_end, max_bars)
            res.trades.extend(trades)
            fold.update(
                params=best,
                train_expectancy_r=best_score,
                test_trades=len(trades),
                test_total_r=sum(t.r_multiple for t in trades),
            )
        res.folds.append(fold)
        start += test_bars
    return res


def verdict(stats: dict, folds: list[dict], min_trades: int = 30) -> tuple[str, str]:
    """Wstepna ocena: 'pass', 'weak' albo 'fail' z uzasadnieniem. Progi sa umowne."""
    n = stats.get("trades", 0)
    if n < min_trades:
        return "fail", f"za malo transakcji poza proba ({n} < {min_trades})"
    active = [f for f in folds if f["test_trades"]]
    share = sum(f["test_total_r"] > 0 for f in active) / len(active) if active else 0.0
    if stats["expectancy_r"] <= 0:
        return "fail", f"ujemna oczekiwana {stats['expectancy_r']:+.2f}R"
    if stats["profit_factor"] >= 1.3 and share >= 0.55:
        return "pass", f"oczekiwana {stats['expectancy_r']:+.2f}R, PF {stats['profit_factor']:.2f}, {share:.0%} okien na plus"
    return "weak", f"dodatnia, ale niestabilna: PF {stats['profit_factor']:.2f}, {share:.0%} okien na plus"
