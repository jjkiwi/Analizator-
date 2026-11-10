from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class Costs:
    """Koszty transakcyjne jako ulamek ceny (0.0003 = 0,03%)."""

    spread_pct: float = 0.0
    swap_long_annual_pct: float = 0.0
    swap_short_annual_pct: float = 0.0


@dataclass(frozen=True)
class Instrument:
    symbol: str  # symbol w XTB
    name: str
    category: str  # indices | commodities | metals | crypto | stocks
    sources: dict[str, str] = field(default_factory=dict)  # nazwa zrodla -> symbol w zrodle
    costs: Costs = field(default_factory=Costs)


@dataclass(frozen=True)
class Signal:
    """Sygnal do recznej decyzji. Poziomy liczone na zamknieciu swiecy sygnalowej."""

    symbol: str
    strategy: str
    time: datetime
    side: int  # +1 long, -1 short
    ref_price: float
    stop_loss: float
    take_profit: float
    rationale: str

    @property
    def direction(self) -> str:
        return "LONG" if self.side > 0 else "SHORT"


@dataclass(frozen=True)
class Trade:
    side: int
    entry_time: datetime
    exit_time: datetime
    entry_price: float
    exit_price: float
    exit_reason: str  # sl | tp | timeout | end
    bars_held: int
    cost: float  # spread + swap, w jednostkach ceny
    cost_r: float  # ten sam koszt w R
    r_multiple: float  # wynik netto w wielokrotnosciach ryzyka poczatkowego
