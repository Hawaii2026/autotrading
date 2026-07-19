"""Walk-forward analysis: the anti-overfitting workhorse of the research loop.

Optimise on an in-sample window, evaluate on the *following* out-of-sample
window, roll forward, and stitch the OOS results together. The stitched OOS
equity curve is the only one you should trust — nothing was tuned on it.

This module is intentionally generic: you supply
  - `optimize(train_bars) -> params`   picks best params on the IS window
  - `run(bars, params)    -> trades`    runs the strategy for given params
and it handles the windowing and aggregation.

See research/backtests/orb/run_orb.py for a worked example.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import pandas as pd

from .metrics import Metrics, compute_metrics


@dataclass
class Window:
    train_start: pd.Timestamp
    train_end: pd.Timestamp
    test_start: pd.Timestamp
    test_end: pd.Timestamp
    params: dict
    oos_metrics: Metrics


def make_windows(index: pd.DatetimeIndex, train_days: int,
                 test_days: int) -> list[tuple]:
    """Rolling (train_start, train_end, test_start, test_end) date windows."""
    days = pd.Index(index.normalize().unique()).sort_values()
    windows = []
    i = 0
    while i + train_days + test_days <= len(days):
        windows.append((
            days[i],
            days[i + train_days - 1],
            days[i + train_days],
            days[i + train_days + test_days - 1],
        ))
        i += test_days  # non-overlapping OOS => a continuous OOS track
    return windows


def walk_forward(
    bars: pd.DataFrame,
    optimize: Callable[[pd.DataFrame], dict],
    run: Callable[[pd.DataFrame, dict], pd.DataFrame],
    train_days: int = 60,
    test_days: int = 20,
) -> tuple[pd.DataFrame, list[Window]]:
    """Return (concatenated_oos_trades, per_window_details).

    `optimize` sees only training bars; `run` is then called on the test bars
    with the chosen params. OOS trade lists are concatenated in time order so
    downstream `compute_metrics` describes genuinely unseen performance.
    """
    all_oos_trades: list[pd.DataFrame] = []
    details: list[Window] = []

    for tr_start, tr_end, te_start, te_end in make_windows(
        bars.index, train_days, test_days
    ):
        train = bars.loc[tr_start:tr_end + pd.Timedelta(days=1)]
        test = bars.loc[te_start:te_end + pd.Timedelta(days=1)]
        if len(train) == 0 or len(test) == 0:
            continue

        params = optimize(train)
        oos_trades = run(test, params)
        all_oos_trades.append(oos_trades)
        details.append(Window(
            train_start=tr_start, train_end=tr_end,
            test_start=te_start, test_end=te_end,
            params=params,
            oos_metrics=compute_metrics(oos_trades),
        ))

    combined = (pd.concat(all_oos_trades, ignore_index=True)
                if all_oos_trades else pd.DataFrame())
    return combined, details


def report(details: list[Window]) -> str:
    """Human-readable per-window OOS summary."""
    lines = ["Walk-forward out-of-sample windows:"]
    for w in details:
        lines.append(
            f"  {w.test_start.date()}..{w.test_end.date()}  "
            f"{w.oos_metrics.summary()}  params={w.params}"
        )
    return "\n".join(lines)
