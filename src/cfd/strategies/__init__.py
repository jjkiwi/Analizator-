from .base import Strategy
from .breakout import DonchianBreakout
from .mean_reversion import MeanReversion
from .trend_pullback import TrendPullback

REGISTRY = {
    "trend_pullback": TrendPullback,
    "donchian_breakout": DonchianBreakout,
    "mean_reversion": MeanReversion,
}

# Male siatki parametrow do walk-forward. Celowo waskie: im wiecej kombinacji,
# tym latwiej dopasowac strategie do szumu.
PARAM_GRIDS = {
    "trend_pullback": {"rsi_low": [35.0, 40.0, 45.0], "tp_atr": [2.0, 3.0, 4.0]},
    "donchian_breakout": {"channel": [20, 40, 55], "tp_atr": [3.0, 4.0, 6.0]},
    "mean_reversion": {"bb_k": [2.0, 2.5], "sl_atr": [1.5, 2.0]},
}

__all__ = ["PARAM_GRIDS", "REGISTRY", "DonchianBreakout", "MeanReversion", "Strategy", "TrendPullback"]
