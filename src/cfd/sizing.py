"""Kalkulator wielkosci pozycji: ile lotow, zeby strata na SL wyniosla zadany procent kapitalu.

Nie sklada zlecen. Wynik trzeba porownac z kalkulatorem w xStation, bo wartosc lota
pochodzi z recznie wpisanej specyfikacji (`config/contracts.yaml`).
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import yaml

DEFAULT_PATH = Path("config/contracts.yaml")


@dataclass(frozen=True)
class ContractSpec:
    """Specyfikacja kontraktu z xStation.

    lot_multiplier: o ile (w walucie instrumentu) zmienia sie wynik 1 lota, gdy cena zmieni sie o 1.0.
    """

    lot_multiplier: float
    currency: str
    min_lot: float = 0.01
    lot_step: float = 0.01

    def __post_init__(self) -> None:
        if self.lot_multiplier <= 0 or self.min_lot <= 0 or self.lot_step <= 0:
            raise ValueError("lot_multiplier, min_lot i lot_step musza byc dodatnie")


@dataclass(frozen=True)
class PositionSize:
    volume: float          # loty po zaokragleniu w dol do kroku
    raw_volume: float      # loty przed zaokragleniem
    risk_amount: float     # dopuszczalna strata w walucie rachunku
    loss_per_lot: float    # strata 1 lota na SL w walucie rachunku
    loss_at_sl: float      # strata przy `volume`
    risk_pct_actual: float
    notional: float        # wartosc nominalna pozycji w walucie rachunku
    below_min_lot: bool    # nawet minimalny wolumen przekracza zadane ryzyko


def load_contracts(path: Path | str = DEFAULT_PATH) -> dict[str, ContractSpec]:
    p = Path(path)
    if not p.exists():
        return {}
    raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    return {sym: ContractSpec(**row) for sym, row in (raw.get("contracts") or {}).items()}


def position_size(entry: float, sl: float, risk_pct: float, equity: float,
                  spec: ContractSpec, fx_rate: float = 1.0) -> PositionSize:
    """fx_rate: ile jednostek waluty rachunku kosztuje 1 jednostka waluty instrumentu (np. USDPLN)."""
    if entry <= 0 or sl <= 0:
        raise ValueError("entry i sl musza byc dodatnie")
    if entry == sl:
        raise ValueError("entry i sl nie moga byc rowne")
    if not 0 < risk_pct <= 100:
        raise ValueError("risk_pct musi byc w przedziale (0, 100]")
    if equity <= 0 or fx_rate <= 0:
        raise ValueError("equity i fx_rate musza byc dodatnie")

    risk_amount = equity * risk_pct / 100
    loss_per_lot = abs(entry - sl) * spec.lot_multiplier * fx_rate
    raw = risk_amount / loss_per_lot
    steps = math.floor(raw / spec.lot_step + 1e-9)
    volume = round(steps * spec.lot_step, 8)
    below = volume < spec.min_lot
    if below:
        volume = 0.0
    loss = volume * loss_per_lot
    return PositionSize(
        volume=volume, raw_volume=raw, risk_amount=risk_amount, loss_per_lot=loss_per_lot,
        loss_at_sl=loss, risk_pct_actual=100 * loss / equity,
        notional=volume * entry * spec.lot_multiplier * fx_rate, below_min_lot=below,
    )
