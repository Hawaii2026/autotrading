"""Run the ORB example the way CLAUDE.md demands: in-sample, then a SEPARATE
out-of-sample verdict, plus a walk-forward pass. Never in-sample alone.

Usage
-----
    # Smoke test on synthetic data (no market data needed — proves the plumbing):
    python -m research.backtests.orb.run_orb --sample --instrument MNQ

    # Real research (once you've exported bars into research/data/):
    python -m research.backtests.orb.run_orb \
        --data research/data/NQ_1min.csv --instrument NQ \
        --is-end 2024-12-31

Run from the repo root so `research` is importable.
"""
from __future__ import annotations

import argparse
import itertools

import pandas as pd

from research.backtests.orb.strategy import generate_signals
from research.lib.backtester import backtest
from research.lib.metrics import compute_metrics
from research.lib.walk_forward import report, walk_forward


def run(bars: pd.DataFrame, params: dict, instrument: str) -> pd.DataFrame:
    signals = generate_signals(
        bars,
        open_minutes=params["open_minutes"],
        stop_ticks=params["stop_ticks"],
        rr=params["rr"],
    )
    return backtest(bars, signals, instrument=instrument, contracts=1)


def make_optimizer(instrument: str):
    """Grid search over a SMALL param set (overfitting guardrail: <20 variants)."""
    grid = [
        {"open_minutes": om, "stop_ticks": st, "rr": rr}
        for om, st, rr in itertools.product([15, 30], [30, 40, 50], [1.5, 2.0, 3.0])
    ]  # 2 x 3 x 3 = 18 variants — under the 20-variant contamination line

    def optimize(train_bars: pd.DataFrame) -> dict:
        best, best_pf = grid[0], -1.0
        for params in grid:
            trades = run(train_bars, params, instrument)
            m = compute_metrics(trades)
            # require a minimum sample so we don't chase a 3-trade fluke
            if m.trade_count >= 20 and m.profit_factor > best_pf:
                best, best_pf = params, m.profit_factor
        return best

    return optimize, grid


def main() -> None:
    ap = argparse.ArgumentParser(description="ORB backtest (IS / OOS / walk-forward)")
    ap.add_argument("--data", help="path to exported bars (NT8 csv or parquet)")
    ap.add_argument("--sample", action="store_true",
                    help="use synthetic data (plumbing smoke test only)")
    ap.add_argument("--instrument", default="MNQ",
                    choices=["NQ", "MNQ", "ES", "MES"])
    ap.add_argument("--is-end", default="2024-12-31",
                    help="last date of the in-sample window (YYYY-MM-DD)")
    args = ap.parse_args()

    if args.sample:
        from research.lib.sample_data import generate_sample_bars
        print("[!] SYNTHETIC data — proves the engine works, says NOTHING about edge.")
        bars = generate_sample_bars(days=180)
    elif args.data:
        from research.lib.data_loader import load_bars
        bars = load_bars(args.data)
    else:
        ap.error("pass --data <file> or --sample")

    optimize, grid = make_optimizer(args.instrument)

    is_bars = bars.loc[:args.is_end]
    oos_bars = bars.loc[args.is_end:].iloc[1:]

    # 1) In-sample: pick params (this WILL look good — that's the point of IS).
    best = optimize(is_bars)
    is_trades = run(is_bars, best, args.instrument)
    print("\n=== IN-SAMPLE (tuned — do not trust in isolation) ===")
    print(f"params={best}")
    print(compute_metrics(is_trades).summary())

    # 2) Out-of-sample: ONE shot, params frozen from IS.
    if len(oos_bars):
        oos_trades = run(oos_bars, best, args.instrument)
        print("\n=== OUT-OF-SAMPLE (sacred — the real verdict) ===")
        print(compute_metrics(oos_trades).summary())
    else:
        print("\n[!] No out-of-sample bars after --is-end; extend your data.")

    # 3) Walk-forward: rolling re-optimisation, stitched OOS track.
    print("\n=== WALK-FORWARD ===")
    combined, details = walk_forward(
        bars,
        optimize=optimize,
        run=lambda b, p: run(b, p, args.instrument),
        train_days=60, test_days=20,
    )
    print(report(details))
    print("\nStitched out-of-sample performance across all walk-forward windows:")
    print(compute_metrics(combined).summary())


if __name__ == "__main__":
    main()
