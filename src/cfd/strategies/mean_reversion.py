from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from ..features import adx, atr, bollinger, rsi


@dataclass
class MeanReversion:
    """Powrot do sredniej w konsolidacji: cena poza wstega Bollingera przy slabym trendzie.

    TP na srodkowej wstedze (nie mniej niz 1 ATR), SL jako wielokrotnosc ATR.
    """

    bb_period: int = 20
    bb_k: float = 2.0
    rsi_period: int = 14
    rsi_low: float = 35.0
    rsi_high: float = 65.0
    adx_period: int = 14
    adx_max: float = 25.0
    atr_period: int = 14
    sl_atr: float = 1.5
    name: str = "mean_reversion"

    def generate(self, df: pd.DataFrame) -> pd.DataFrame:
        close = df["close"]
        bb = bollinger(close, self.bb_period, self.bb_k)
        r, a, strength = rsi(close, self.rsi_period), atr(df, self.atr_period), adx(df, self.adx_period)
        calm = strength < self.adx_max
        long_sig = calm & (close < bb["lower"]) & (r < self.rsi_low)
        short_sig = calm & (close > bb["upper"]) & (r > self.rsi_high)
        out = pd.DataFrame(index=df.index)
        out["side"] = np.where(long_sig, 1, np.where(short_sig, -1, 0))
        out["sl_dist"] = a * self.sl_atr
        out["tp_dist"] = np.maximum((bb["mid"] - close).abs(), a)
        out.loc[a.isna() | strength.isna() | bb["mid"].isna(), "side"] = 0
        out["rationale"] = ""
        out.loc[out["side"] == 1, "rationale"] = f"Konsolidacja (ADX<{self.adx_max:.0f}), cena pod dolna wstega, RSI<{self.rsi_low:.0f}"
        out.loc[out["side"] == -1, "rationale"] = f"Konsolidacja (ADX<{self.adx_max:.0f}), cena nad gorna wstega, RSI>{self.rsi_high:.0f}"
        return out
