"""Quantify how far KarenBridge-derived bars are from NT8's real bars.

KarenBridge samples at ~2 ticks/sec (latest-value), so bars built from its
feed are approximations. This tool measures the approximation error for an
overlapping day so the number is KNOWN instead of assumed:

    python tools/check_karen_fidelity.py \
        research/data/ticks/MNQ_09-26/2026-07-21.parquet \
        research/data/MNQ_1min.csv \
        --instrument MNQ [--shift-minutes 0]

It resamples the recorded ticks to 1-min OHLC, aligns them with the NT8
export on shared timestamps, and reports per-field deltas in ticks, flagging
every bar off by more than 1 tick.

Two caveats printed with every run:
  - VOLUME is not comparable (Karen only carries sampled last-trade sizes).
  - Time zones: Karen records UTC; NT8 exports chart-local time. Use
    --shift-minutes to align (e.g. -240 for ET daylight time).

Whatever this reports, the conclusion is already fixed by the sampling
design: Karen bars are for display/monitoring — research uses NT8 exports.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

from research.lib.data_loader import load_bars
from research.lib.instruments import get_instrument


def karen_ticks_to_bars(path: Path, rule: str = "1min") -> pd.DataFrame:
    if path.suffix == ".parquet":
        ticks = pd.read_parquet(path)
    else:
        ticks = pd.read_csv(path)
    ticks["market_time"] = pd.to_datetime(ticks["market_time"], utc=True)
    ticks = ticks.sort_values("market_time").set_index("market_time")
    bars = ticks["price"].resample(rule, label="right", closed="right").agg(
        ["first", "max", "min", "last"])
    bars.columns = ["open", "high", "low", "close"]
    return bars.dropna()


def main() -> int:
    ap = argparse.ArgumentParser(description="Karen bars vs NT8 bars, one day.")
    ap.add_argument("karen_ticks", help="daily parquet/csv from tick_recorder")
    ap.add_argument("nt8_bars", help="NT8 1-min export covering the same day")
    ap.add_argument("--instrument", default="MNQ",
                    choices=["NQ", "MNQ", "ES", "MES"])
    ap.add_argument("--shift-minutes", type=int, default=0,
                    help="add this many minutes to Karen timestamps to match "
                         "the NT8 export's clock (UTC vs chart-local)")
    args = ap.parse_args()

    tick = get_instrument(args.instrument).tick_size

    karen = karen_ticks_to_bars(Path(args.karen_ticks))
    karen.index = karen.index.tz_localize(None) + pd.Timedelta(
        minutes=args.shift_minutes)
    nt8 = load_bars(args.nt8_bars)

    shared = karen.index.intersection(nt8.index)
    print(f"Karen bars: {len(karen)}   NT8 bars in file: {len(nt8)}   "
          f"overlapping minutes: {len(shared)}")
    if len(shared) < 30:
        print("\nToo little overlap to judge (need 30+ shared minutes). "
              "Check --shift-minutes — Karen is UTC, NT8 is chart-local.")
        return 1

    k, n = karen.loc[shared], nt8.loc[shared]
    print(f"\nPer-field |delta| in ticks over {len(shared)} shared bars "
          f"(bars off by >1 tick flagged):")
    total_flagged = set()
    for field in ["open", "high", "low", "close"]:
        d = (k[field] - n[field]).abs() / tick
        flagged = d[d > 1.0]
        total_flagged.update(flagged.index)
        print(f"  {field:<5} mean {d.mean():5.2f}  p95 {d.quantile(0.95):5.2f}  "
              f"max {d.max():6.2f}   bars >1 tick: {len(flagged)} "
              f"({len(flagged) / len(shared):.1%})")

    print(f"\nBars with ANY field off by >1 tick: {len(total_flagged)} "
          f"of {len(shared)} ({len(total_flagged) / len(shared):.1%})")
    print("\nCaveats: volume not compared (Karen's is sampled, not true); "
          "highs/lows are where 2 Hz sampling loses the most.")
    print("Conclusion stands regardless of the numbers: Karen feed = display/"
          "monitoring; research bars come from NT8 exports (CLAUDE.md).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
