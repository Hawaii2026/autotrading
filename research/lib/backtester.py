"""A small, honest bracket backtester for intraday futures.

Design goals (mirrors how the NinjaScript port behaves so the two trade lists
tell the same story):

- Signals are evaluated on bar CLOSE (``OnBarClose`` semantics). An entry
  therefore fills at the NEXT bar's open.
- Every entry carries a protective STOP (CLAUDE.md: "every entry has a stop
  attached before entry submission"). A target is optional.
- Costs are real: commission per round turn + configurable slippage per side,
  taken from ``instruments.py``. Metrics downstream are always net of these.
- One position at a time (no pyramiding) — matches the simple strategies this
  lab starts with.

Ambiguity rule: if both stop and target could fill inside the same bar, we
assume the STOP filled first. That is the pessimistic assumption, on purpose.

Usage
-----
    from research.lib.backtester import backtest
    trades = backtest(bars, signals, instrument="MNQ", contracts=1)
    from research.lib.metrics import compute_metrics
    print(compute_metrics(trades).summary())

`signals` is a DataFrame aligned to `bars.index` with columns:
    signal : +1 enter long, -1 enter short, 0 do nothing (checked at bar close)
    stop   : protective stop price for that entry (required when signal != 0)
    target : profit target price (optional; NaN = manage by stop / exit only)
    exit   : optional bool; True forces any open position flat at next open
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .instruments import get_instrument

_TRADE_COLUMNS = [
    "entry_time", "exit_time", "direction", "entry_price", "exit_price",
    "contracts", "reason", "bars_held", "gross_pnl", "commission", "net_pnl",
]


def backtest(
    bars: pd.DataFrame,
    signals: pd.DataFrame,
    instrument: str,
    contracts: int = 1,
    slippage_ticks: float = 1.0,
    session_flat: bool = True,
) -> pd.DataFrame:
    """Run the bracket simulation and return a trades DataFrame.

    Parameters
    ----------
    bars : OHLC(V) frame with a DatetimeIndex (from data_loader.load_bars).
    signals : aligned frame with signal/stop/target[/exit] columns.
    instrument : key into INSTRUMENTS ("NQ"/"MNQ"/"ES"/"MES").
    contracts : position size.
    slippage_ticks : ticks of adverse slippage assumed on each fill (per side).
    session_flat : if True, force flat at the last bar of each calendar day
        (intraday strategies do not hold overnight).
    """
    inst = get_instrument(instrument)
    tick = inst.tick_size
    slip = slippage_ticks * tick

    bars = bars.sort_index()
    sig = signals.reindex(bars.index)
    signal = sig["signal"].fillna(0).to_numpy()
    stop = sig["stop"].to_numpy() if "stop" in sig else np.full(len(bars), np.nan)
    target = sig["target"].to_numpy() if "target" in sig else np.full(len(bars), np.nan)
    force_exit = (sig["exit"].fillna(False).to_numpy()
                  if "exit" in sig else np.zeros(len(bars), dtype=bool))

    o = bars["open"].to_numpy()
    h = bars["high"].to_numpy()
    l = bars["low"].to_numpy()
    c = bars["close"].to_numpy()
    idx = bars.index
    day = idx.normalize().to_numpy()

    n = len(bars)
    trades: list[dict] = []

    pos = 0            # 0 flat, +1 long, -1 short
    entry_price = 0.0
    entry_i = -1
    cur_stop = np.nan
    cur_target = np.nan

    def close_trade(exit_i: int, exit_px: float, reason: str) -> None:
        nonlocal pos
        # slippage always adverse to us on exit
        fill = exit_px - slip if pos > 0 else exit_px + slip
        gross = (fill - entry_price) * pos * inst.point_value * contracts
        commission = inst.round_turn_cost(contracts)
        trades.append({
            "entry_time": idx[entry_i],
            "exit_time": idx[exit_i],
            "direction": "long" if pos > 0 else "short",
            "entry_price": entry_price,
            "exit_price": fill,
            "contracts": contracts,
            "reason": reason,
            "bars_held": exit_i - entry_i,
            "gross_pnl": gross,
            "commission": commission,
            "net_pnl": gross - commission,
        })
        pos = 0

    for i in range(n):
        # --- manage an open position on THIS bar (intrabar stop/target) ---
        if pos != 0:
            last_of_day = session_flat and (i + 1 >= n or day[i + 1] != day[i])
            if pos > 0:
                hit_stop = not np.isnan(cur_stop) and l[i] <= cur_stop
                hit_tgt = not np.isnan(cur_target) and h[i] >= cur_target
                if hit_stop:                       # stop first (pessimistic)
                    close_trade(i, cur_stop, "stop")
                elif hit_tgt:
                    close_trade(i, cur_target, "target")
            else:
                hit_stop = not np.isnan(cur_stop) and h[i] >= cur_stop
                hit_tgt = not np.isnan(cur_target) and l[i] <= cur_target
                if hit_stop:
                    close_trade(i, cur_stop, "stop")
                elif hit_tgt:
                    close_trade(i, cur_target, "target")

            if pos != 0 and (force_exit[i] or last_of_day):
                close_trade(i, c[i], "session" if last_of_day else "exit")

        # --- act on a signal from the PREVIOUS bar's close: fill at this open ---
        if pos == 0 and i > 0 and signal[i - 1] != 0:
            direction = int(np.sign(signal[i - 1]))
            s = stop[i - 1]
            if np.isnan(s):
                # No stop => reject the entry. A stopless entry is a bug, not a trade.
                continue
            pos = direction
            entry_i = i
            # adverse slippage on entry too
            entry_price = o[i] + slip if pos > 0 else o[i] - slip
            cur_stop = s
            cur_target = target[i - 1]

    # close anything still open at the very end
    if pos != 0:
        close_trade(n - 1, c[n - 1], "eod")

    return pd.DataFrame(trades, columns=_TRADE_COLUMNS)
