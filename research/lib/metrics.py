"""Performance metrics for a list of closed trades.

Every backtest reports the same honest set of numbers (CLAUDE.md non-negotiable):
trade count, profit factor, max drawdown, win rate, average trade — all AFTER
commissions and slippage, because the trades passed in already have net P&L.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd


@dataclass
class Metrics:
    trade_count: int
    net_pnl: float
    gross_profit: float
    gross_loss: float
    profit_factor: float          # gross_profit / abs(gross_loss); inf if no losers
    win_rate: float               # fraction of trades with pnl > 0
    avg_trade: float              # net P&L per trade
    avg_win: float
    avg_loss: float
    expectancy: float             # same as avg_trade, named for clarity
    max_drawdown: float           # peak-to-trough of the cumulative equity curve ($)
    max_drawdown_pct: float       # relative to peak equity, if peak > 0
    largest_win: float
    largest_loss: float
    max_consecutive_losses: int

    def as_dict(self) -> dict:
        return asdict(self)

    def summary(self) -> str:
        return (
            f"trades={self.trade_count}  net=${self.net_pnl:,.0f}  "
            f"PF={self.profit_factor:.2f}  win%={self.win_rate * 100:.1f}  "
            f"avg=${self.avg_trade:,.1f}  maxDD=${self.max_drawdown:,.0f}"
        )


def _max_drawdown(equity: np.ndarray) -> tuple[float, float]:
    """Return (max_drawdown_dollars, max_drawdown_pct) from an equity curve."""
    if equity.size == 0:
        return 0.0, 0.0
    running_peak = np.maximum.accumulate(equity)
    drawdowns = running_peak - equity
    i = int(np.argmax(drawdowns))
    max_dd = float(drawdowns[i])
    peak = float(running_peak[i])
    max_dd_pct = (max_dd / peak) if peak > 0 else 0.0
    return max_dd, max_dd_pct


def _max_consecutive_losses(pnl: np.ndarray) -> int:
    worst = run = 0
    for x in pnl:
        if x < 0:
            run += 1
            worst = max(worst, run)
        else:
            run = 0
    return worst


def compute_metrics(trades: pd.DataFrame, pnl_col: str = "net_pnl") -> Metrics:
    """Compute metrics from a trades DataFrame.

    `trades` must have a numeric `pnl_col` of per-trade net P&L in dollars,
    ordered chronologically (exit order). Returns a `Metrics` dataclass.
    """
    if trades is None or len(trades) == 0:
        return Metrics(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)

    pnl = trades[pnl_col].to_numpy(dtype=float)
    wins = pnl[pnl > 0]
    losses = pnl[pnl < 0]

    gross_profit = float(wins.sum())
    gross_loss = float(losses.sum())  # negative
    profit_factor = (
        gross_profit / abs(gross_loss) if gross_loss != 0
        else (float("inf") if gross_profit > 0 else 0.0)
    )

    equity = np.cumsum(pnl)
    max_dd, max_dd_pct = _max_drawdown(equity)

    return Metrics(
        trade_count=int(len(pnl)),
        net_pnl=float(pnl.sum()),
        gross_profit=gross_profit,
        gross_loss=gross_loss,
        profit_factor=profit_factor,
        win_rate=float(len(wins) / len(pnl)),
        avg_trade=float(pnl.mean()),
        avg_win=float(wins.mean()) if wins.size else 0.0,
        avg_loss=float(losses.mean()) if losses.size else 0.0,
        expectancy=float(pnl.mean()),
        max_drawdown=max_dd,
        max_drawdown_pct=max_dd_pct,
        largest_win=float(pnl.max()),
        largest_loss=float(pnl.min()),
        max_consecutive_losses=_max_consecutive_losses(pnl),
    )


def equity_curve(trades: pd.DataFrame, pnl_col: str = "net_pnl") -> pd.Series:
    """Cumulative net P&L indexed by exit time (or trade number if no exit time)."""
    if trades is None or len(trades) == 0:
        return pd.Series(dtype=float)
    cum = trades[pnl_col].cumsum()
    if "exit_time" in trades.columns:
        cum.index = pd.to_datetime(trades["exit_time"])
    return cum
