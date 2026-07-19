"""Phase 3 port-fidelity check: compare the Python backtest's trade list with
the NinjaScript port's trade list from NT8's Strategy Analyzer.

The two will never match perfectly (bar building and fill assumptions differ) —
the question is whether they tell the SAME STORY: same trades at the same times
in the same direction, with small, explainable price/P&L deltas.

Usage
-----
    # 1) dump the Python side (from any backtest run):
    #      trades.to_csv("research/backtests/orb/python_trades.csv", index=False)
    # 2) in NT8: Strategy Analyzer -> run the port over the same window ->
    #      Trades tab -> right-click -> Export -> save as nt8_trades.csv
    # 3) compare:
    python tools/compare_trades.py python_trades.csv nt8_trades.csv \
        --instrument NQ --tolerance-min 3

Exit code 0 when the lists tell the same story (>=80% matched both ways and no
systematic price bias beyond a few ticks); 1 otherwise. Paste the report into
Claude Code to diagnose discrepancies.
"""
from __future__ import annotations

import argparse
import sys
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

from research.lib.instruments import get_instrument

# forgiving column aliases for the NT8 Strategy Analyzer trades export
NT8_ALIASES = {
    "entry_time": ["entry time", "entry", "entrytime"],
    "exit_time": ["exit time", "exit", "exittime"],
    "direction": ["market pos.", "market position", "position", "direction"],
    "entry_price": ["entry price", "entryprice"],
    "exit_price": ["exit price", "exitprice"],
    "pnl": ["profit", "pnl", "net profit", "profit currency"],
    "qty": ["qty", "quantity"],
}


def _pick(df: pd.DataFrame, names: list[str]) -> str | None:
    lower = {c.lower().strip(): c for c in df.columns}
    for n in names:
        if n in lower:
            return lower[n]
    return None


def _money(s):
    return pd.to_numeric(
        s.astype(str).str.replace(r"[$,()]", "", regex=True), errors="coerce"
    )


def load_python_trades(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    need = {"entry_time", "exit_time", "direction", "entry_price", "exit_price", "net_pnl"}
    missing = need - set(df.columns)
    if missing:
        raise SystemExit(f"{path}: missing columns {sorted(missing)} — "
                         "export with trades.to_csv(..., index=False)")
    df["entry_time"] = pd.to_datetime(df["entry_time"])
    df["exit_time"] = pd.to_datetime(df["exit_time"])
    df["direction"] = df["direction"].str.lower().str.strip()
    df = df.rename(columns={"net_pnl": "pnl"})
    return df[["entry_time", "exit_time", "direction", "entry_price", "exit_price", "pnl"]]


def load_nt8_trades(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    cols = {k: _pick(df, v) for k, v in NT8_ALIASES.items()}
    need = ["entry_time", "exit_time", "direction", "entry_price", "exit_price", "pnl"]
    missing = [k for k in need if not cols[k]]
    if missing:
        raise SystemExit(f"{path}: could not find columns for {missing}. "
                         f"Columns seen: {list(df.columns)} — extend NT8_ALIASES.")
    out = pd.DataFrame({
        "entry_time": pd.to_datetime(df[cols["entry_time"]], errors="coerce"),
        "exit_time": pd.to_datetime(df[cols["exit_time"]], errors="coerce"),
        "direction": df[cols["direction"]].astype(str).str.lower().str.strip(),
        "entry_price": _money(df[cols["entry_price"]]),
        "exit_price": _money(df[cols["exit_price"]]),
        "pnl": _money(df[cols["pnl"]]),
    }).dropna(subset=["entry_time", "direction"])
    out["direction"] = out["direction"].replace({"long": "long", "short": "short"})
    return out.sort_values("entry_time").reset_index(drop=True)


def match_trades(py: pd.DataFrame, nt: pd.DataFrame, tol: timedelta):
    """Greedy nearest-entry-time matching, same direction, within tolerance."""
    used_nt: set[int] = set()
    pairs: list[tuple[int, int]] = []
    for i, row in py.iterrows():
        candidates = [
            (abs((nt.at[j, "entry_time"] - row["entry_time"]).total_seconds()), j)
            for j in nt.index
            if j not in used_nt
            and nt.at[j, "direction"] == row["direction"]
            and abs(nt.at[j, "entry_time"] - row["entry_time"]) <= tol
        ]
        if candidates:
            _, j = min(candidates)
            used_nt.add(j)
            pairs.append((i, j))
    unmatched_py = [i for i in py.index if i not in {p for p, _ in pairs}]
    unmatched_nt = [j for j in nt.index if j not in used_nt]
    return pairs, unmatched_py, unmatched_nt


def main() -> int:
    ap = argparse.ArgumentParser(description="Compare Python vs NT8 trade lists.")
    ap.add_argument("python_csv")
    ap.add_argument("nt8_csv")
    ap.add_argument("--instrument", default="NQ", choices=["NQ", "MNQ", "ES", "MES"])
    ap.add_argument("--tolerance-min", type=float, default=3.0,
                    help="entry-time match window in minutes (default 3)")
    args = ap.parse_args()

    inst = get_instrument(args.instrument)
    py = load_python_trades(args.python_csv)
    nt = load_nt8_trades(args.nt8_csv)
    tol = timedelta(minutes=args.tolerance_min)

    pairs, un_py, un_nt = match_trades(py, nt, tol)

    print(f"Python trades: {len(py)}   NT8 trades: {len(nt)}   "
          f"matched: {len(pairs)}  (tolerance ±{args.tolerance_min:g} min)")

    if pairs:
        rows = []
        for i, j in pairs:
            entry_d = (nt.at[j, "entry_price"] - py.at[i, "entry_price"]) / inst.tick_size
            exit_d = (nt.at[j, "exit_price"] - py.at[i, "exit_price"]) / inst.tick_size
            pnl_d = nt.at[j, "pnl"] - py.at[i, "pnl"]
            rows.append((entry_d, exit_d, pnl_d))
        d = pd.DataFrame(rows, columns=["entry_ticks", "exit_ticks", "pnl_delta"])
        print("\nMatched-pair deltas (NT8 minus Python):")
        print(f"  entry: mean {d.entry_ticks.mean():+.2f} ticks, "
              f"mean abs {d.entry_ticks.abs().mean():.2f}, worst {d.entry_ticks.abs().max():.1f}")
        print(f"  exit : mean {d.exit_ticks.mean():+.2f} ticks, "
              f"mean abs {d.exit_ticks.abs().mean():.2f}, worst {d.exit_ticks.abs().max():.1f}")
        print(f"  P&L  : total {d.pnl_delta.sum():+,.0f} $, "
              f"mean {d.pnl_delta.mean():+,.1f} $/trade")

    def show(label, frame, ids):
        if not ids:
            return
        print(f"\n{label} ({len(ids)}):")
        for k in ids[:10]:
            r = frame.loc[k]
            print(f"  {r['entry_time']}  {r['direction']:<5} "
                  f"entry {r['entry_price']}  pnl {r['pnl']:+,.0f}")
        if len(ids) > 10:
            print(f"  ... and {len(ids) - 10} more")

    show("Only in Python (NT8 missed or timed differently)", py, un_py)
    show("Only in NT8 (Python missed or timed differently)", nt, un_nt)

    # verdict: same story?
    match_rate = len(pairs) / max(len(py), len(nt)) if max(len(py), len(nt)) else 0
    bias_ok = True
    if pairs:
        bias_ok = abs(d.entry_ticks.mean()) <= 4 and abs(d.exit_ticks.mean()) <= 4
    ok = match_rate >= 0.8 and bias_ok

    print("\nVerdict:", "SAME STORY ✓" if ok else "DIVERGENT ✗")
    if not ok:
        if match_rate < 0.8:
            print(f"  match rate {match_rate:.0%} < 80% — check session template, "
                  "bar series, and the entry-window clock (time zones!).")
        if not bias_ok:
            print("  systematic entry/exit price bias > 4 ticks — check fill "
                  "assumptions (slippage setting vs Analyzer fill model).")
        print("  Paste this report plus both CSV heads into Claude Code to diagnose.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
