from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from ..features import atr, ema, rsi


@dataclass
class TrendPullback:
    """Wejscie z trendem po korekcie.

    Long: EMA szybka > EMA wolna, cena nad EMA wolna, RSI wraca powyzej progu
    wyprzedania korekty. Short symetrycznie. SL i TP jako wielokrotnosc ATR.

    Parametry sa celowo "okragle" i nieoptymalizowane. To strategia bazowa
    do sprawdzenia calego toru, a nie gotowy system.
    """

    fast: int = 50
    slow: int = 200
    rsi_period: int = 14
    rsi_low: float = 40.0
    rsi_high: float = 60.0
    atr_period: int = 14
    sl_atr: float = 2.0
    tp_atr: float = 3.0
    name: str = "trend_pullback"

    def generate(self, df: pd.DataFrame) -> pd.DataFrame:
        close = df["close"]
        e_fast, e_slow = ema(close, self.fast), ema(close, self.slow)
        r = rsi(close, self.rsi_period)
        a = atr(df, self.atr_period)
        r_prev = r.shift(1)

        up = (e_fast > e_slow) & (close > e_slow)
        down = (e_fast < e_slow) & (close < e_slow)
        long_sig = up & (r_prev < self.rsi_low) & (r >= self.rsi_low)
        short_sig = down & (r_prev > self.rsi_high) & (r <= self.rsi_high)

        side = np.where(long_sig, 1, np.where(short_sig, -1, 0))
        out = pd.DataFrame(index=df.index)
        out["side"] = side
        out["sl_dist"] = a * self.sl_atr
        out["tp_dist"] = a * self.tp_atr
        out.loc[a.isna() | e_slow.isna(), "side"] = 0
        out["rationale"] = ""
        out.loc[out["side"] == 1, "rationale"] = (
            f"Trend wzrostowy (EMA{self.fast}>EMA{self.slow}), RSI wrocil nad {self.rsi_low:.0f}"
        )
        out.loc[out["side"] == -1, "rationale"] = (
            f"Trend spadkowy (EMA{self.fast}<EMA{self.slow}), RSI wrocil pod {self.rsi_high:.0f}"
        )
        return out
