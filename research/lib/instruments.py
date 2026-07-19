"""Instrument specifications for NQ/MNQ and ES/MES.

Point values, tick sizes, and commission assumptions live in ONE place so no
backtest ever silently mixes mini economics with micro contracts. See CLAUDE.md.

Commissions are per-side, per-contract estimates (round turn = 2x these). Adjust
`commission_per_side` to match your actual broker/prop-firm rate — the defaults
are conservative retail-ish futures rates so backtests err toward pessimism.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Instrument:
    symbol: str
    point_value: float          # dollars per 1.0 point move, per contract
    tick_size: float            # smallest price increment
    commission_per_side: float  # dollars per contract, per side (entry OR exit)

    @property
    def tick_value(self) -> float:
        """Dollars per tick, per contract."""
        return self.point_value * self.tick_size

    def round_turn_cost(self, contracts: int = 1) -> float:
        """Total commission for a full round turn (in + out)."""
        return 2 * self.commission_per_side * contracts

    def slippage_cost(self, slippage_ticks: float, contracts: int = 1) -> float:
        """Dollar cost of `slippage_ticks` of slippage per side, both sides."""
        return 2 * slippage_ticks * self.tick_value * contracts


# Micros track their minis tick-for-tick; only the point value (and thus the
# relative weight of costs) changes.
INSTRUMENTS: dict[str, Instrument] = {
    "NQ":  Instrument("NQ",  point_value=20.0, tick_size=0.25, commission_per_side=1.34),
    "MNQ": Instrument("MNQ", point_value=2.0,  tick_size=0.25, commission_per_side=0.37),
    "ES":  Instrument("ES",  point_value=50.0, tick_size=0.25, commission_per_side=1.34),
    "MES": Instrument("MES", point_value=5.0,  tick_size=0.25, commission_per_side=0.37),
}


def get_instrument(symbol: str) -> Instrument:
    key = symbol.upper()
    if key not in INSTRUMENTS:
        raise KeyError(
            f"Unknown instrument {symbol!r}. Known: {sorted(INSTRUMENTS)}. "
            "Add it to research/lib/instruments.py."
        )
    return INSTRUMENTS[key]
