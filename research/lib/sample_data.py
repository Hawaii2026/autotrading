"""Deterministic synthetic intraday bars — for smoke-testing the engine only.

This is NOT market data and must never be used to judge a strategy's edge. It
exists so the backtester, walk-forward, and metrics code can be exercised
end-to-end (and CI can run) before you have exported real NQ/ES bars.

No randomness source that would break reproducibility: a fixed seed is passed in.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def generate_sample_bars(
    days: int = 120,
    start: str = "2024-01-01",
    bars_per_day: int = 390,     # ~ a 6.5h RTH session in 1-min bars
    seed: int = 42,
    start_price: float = 18000.0,
    tick: float = 0.25,
) -> pd.DataFrame:
    """Return a synthetic 1-min OHLCV frame (weekdays only, RTH-ish clock)."""
    rng = np.random.default_rng(seed)
    sessions = pd.bdate_range(start=start, periods=days)

    frames = []
    price = start_price
    for d in sessions:
        session_open = d + pd.Timedelta(hours=9, minutes=30)
        times = session_open + pd.to_timedelta(np.arange(bars_per_day), unit="m")
        # small drift + noise; occasional trend day so breakouts have something to do
        drift = rng.normal(0, 0.3) * (1 if rng.random() > 0.5 else -1)
        steps = rng.normal(drift, 3.0, size=bars_per_day)
        closes = price + np.cumsum(steps)
        opens = np.concatenate([[price], closes[:-1]])
        highs = np.maximum(opens, closes) + np.abs(rng.normal(0, 1.5, bars_per_day))
        lows = np.minimum(opens, closes) - np.abs(rng.normal(0, 1.5, bars_per_day))
        vol = rng.integers(100, 2000, bars_per_day).astype(float)
        price = closes[-1]

        df = pd.DataFrame(
            {"open": opens, "high": highs, "low": lows, "close": closes, "volume": vol},
            index=times,
        )
        frames.append(df)

    bars = pd.concat(frames)
    # snap to tick grid so prices look like real futures
    for col in ["open", "high", "low", "close"]:
        bars[col] = (bars[col] / tick).round() * tick
    return bars
