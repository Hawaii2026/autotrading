"""Opening-Range Breakout (ORB) — a worked example strategy for the research lab.

The "why" in one sentence (CLAUDE.md prefers an edge you can state): the first
N minutes of the RTH session set a range; a decisive break of that range often
initiates the day's directional move, and we ride it with a fixed R:R bracket.

This module only produces SIGNALS. The engine (research/lib/backtester.py) turns
them into fills, costs, and trades. Keeping signal-generation pure makes it
trivial to compare against the NinjaScript port later.

Parameters (the only things walk-forward is allowed to tune):
    open_minutes : length of the opening range in minutes
    stop_ticks   : protective stop distance from entry, in ticks
    rr           : reward-to-risk multiple for the target
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def generate_signals(
    bars: pd.DataFrame,
    open_minutes: int = 15,
    stop_ticks: int = 40,
    rr: float = 2.0,
    tick: float = 0.25,
    session_start: str = "09:30",
    no_entry_after: str = "12:00",
) -> pd.DataFrame:
    """Return a signals frame aligned to `bars.index`.

    One entry attempt per side per day: the first bar that closes beyond the
    opening range triggers a stop/target bracket in that direction. No new
    entries after `no_entry_after` (avoid the dead midday chop).
    """
    idx = bars.index
    signal = np.zeros(len(bars))
    stop = np.full(len(bars), np.nan)
    target = np.full(len(bars), np.nan)

    stop_dist = stop_ticks * tick
    day = idx.normalize()

    for _, day_idx in pd.Series(range(len(bars)), index=idx).groupby(day):
        rows = day_idx.to_numpy()
        session = idx[rows]
        # opening range = bars within the first `open_minutes` from session_start
        s_open = session[0].normalize() + pd.Timedelta(
            hours=int(session_start[:2]), minutes=int(session_start[3:])
        )
        or_end = s_open + pd.Timedelta(minutes=open_minutes)
        cutoff = session[0].normalize() + pd.Timedelta(
            hours=int(no_entry_after[:2]), minutes=int(no_entry_after[3:])
        )

        in_or = (session >= s_open) & (session < or_end)
        if not in_or.any():
            continue
        or_high = bars["high"].to_numpy()[rows][in_or].max()
        or_low = bars["low"].to_numpy()[rows][in_or].min()

        fired = False
        highs = bars["high"].to_numpy()[rows]
        lows = bars["low"].to_numpy()[rows]
        closes = bars["close"].to_numpy()[rows]
        for k in range(len(rows)):
            t = session[k]
            if fired or t < or_end or t > cutoff:
                continue
            if closes[k] > or_high:                     # long breakout
                entry_ref = closes[k]
                signal[rows[k]] = 1
                stop[rows[k]] = entry_ref - stop_dist
                target[rows[k]] = entry_ref + rr * stop_dist
                fired = True
            elif closes[k] < or_low:                    # short breakout
                entry_ref = closes[k]
                signal[rows[k]] = -1
                stop[rows[k]] = entry_ref + stop_dist
                target[rows[k]] = entry_ref - rr * stop_dist
                fired = True

    return pd.DataFrame(
        {"signal": signal, "stop": stop, "target": target}, index=idx
    )
