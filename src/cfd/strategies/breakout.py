from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from ..features import adx, atr, donchian


@dataclass
class DonchianBreakout:
    """Wybicie z kanalu N poprzednich swiec, filtrowane sila trendu (ADX)."""

    channel: int = 20
    adx_period: int = 14
    adx_min: float = 20.0
    atr_period: int = 14
    sl_atr: float = 2.0
    tp_atr: float = 4.0
    name: str = "donchian_breakout"

    def generate(self, df: pd.DataFrame) -> pd.DataFrame:
        ch = donchian(df, self.channel)
        a, strength = atr(df, self.atr_period), adx(df, self.adx_period)
        close, prev = df["close"], df["close"].shift(1)
        # Sygnal tylko na swiecy, ktora pierwsza zamyka sie poza kanalem.
        long_sig = (close > ch["upper"]) & (prev <= ch["upper"].shift(1)) & (strength >= self.adx_min)
        short_sig = (close < ch["lower"]) & (prev >= ch["lower"].shift(1)) & (strength >= self.adx_min)
        out = pd.DataFrame(index=df.index)
        out["side"] = np.where(long_sig, 1, np.where(short_sig, -1, 0))
        out["sl_dist"] = a * self.sl_atr
        out["tp_dist"] = a * self.tp_atr
        out.loc[a.isna() | strength.isna(), "side"] = 0
        out["rationale"] = ""
        out.loc[out["side"] == 1, "rationale"] = f"Wybicie gora z kanalu {self.channel} swiec, ADX>={self.adx_min:.0f}"
        out.loc[out["side"] == -1, "rationale"] = f"Wybicie dolem z kanalu {self.channel} swiec, ADX>={self.adx_min:.0f}"
        return out
