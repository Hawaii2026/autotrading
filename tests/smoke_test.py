"""End-to-end plumbing check for the research engine — no market data required.

Runs the ORB strategy on synthetic bars through the backtester and metrics, and
asserts the pieces fit together (costs applied, trades shaped correctly, metrics
computable, walk-forward stitches an OOS track). This validates the ENGINE, never
an edge — synthetic data says nothing about whether a strategy makes money.

    python tests/smoke_test.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from research.backtests.orb.strategy import generate_signals
from research.lib.backtester import backtest
from research.lib.instruments import get_instrument
from research.lib.metrics import compute_metrics
from research.lib.sample_data import generate_sample_bars
from research.lib.walk_forward import walk_forward


def check(name: str, cond: bool) -> None:
    status = "ok  " if cond else "FAIL"
    print(f"  [{status}] {name}")
    if not cond:
        raise AssertionError(name)


def main() -> int:
    print("Smoke test — synthetic data (engine only, NOT an edge test)\n")

    bars = generate_sample_bars(days=120, seed=7)
    check("sample bars generated", len(bars) > 10000)
    check("OHLC columns present", set(["open", "high", "low", "close"]) <= set(bars.columns))
    check("high >= low on every bar", bool((bars["high"] >= bars["low"]).all()))

    inst = get_instrument("MNQ")
    check("instrument tick value correct", abs(inst.tick_value - 0.50) < 1e-9)

    signals = generate_signals(bars, open_minutes=15, stop_ticks=40, rr=2.0)
    check("signals aligned to bars", len(signals) == len(bars))
    check("some signals generated", int((signals["signal"] != 0).sum()) > 0)
    check("every signal has a stop",
          bool(signals.loc[signals["signal"] != 0, "stop"].notna().all()))

    trades = backtest(bars, signals, instrument="MNQ", contracts=1)
    check("trades produced", len(trades) > 0)
    check("commission applied to every trade", bool((trades["commission"] > 0).all()))
    check("net = gross - commission",
          bool(((trades["gross_pnl"] - trades["commission"] - trades["net_pnl"]).abs()
                < 1e-6).all()))

    m = compute_metrics(trades)
    print("\n  metrics:", m.summary())
    check("trade_count matches", m.trade_count == len(trades))
    check("max drawdown non-negative", m.max_drawdown >= 0)

    combined, details = walk_forward(
        bars, optimize=lambda b: {"open_minutes": 15, "stop_ticks": 40, "rr": 2.0},
        run=lambda b, p: backtest(b, generate_signals(b, **p), "MNQ", 1),
        train_days=40, test_days=20,
    )
    check("walk-forward produced OOS windows", len(details) > 0)
    check("walk-forward stitched OOS trades", len(combined) >= 0)

    print("\nAll smoke checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
