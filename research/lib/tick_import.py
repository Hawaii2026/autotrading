"""Import TickRecorder (NT8-side) tick files into the research lab.

This is the RESEARCH-GRADE path — unlike the KarenBridge capture
(display-grade, see research/data/ticks/README.md), TickRecorder.cs writes
every Last tick locally with NT8's own clock, so bars built from it are
legitimate backtest inputs ONCE validated against an NT8 chart export.

Source files (from ninjascript/addons/TickRecorder.cs):
    <Documents>\\NinjaTrader 8\\tickdata\\<INSTRUMENT>\\<yyyy-MM-dd>.csv
    header: time;price;volume     time = "yyyy-MM-dd HH:mm:ss.fff" (NT8 local)

Usage
-----
    # convert raw CSVs to parquet under research/data/ticks_nt8/:
    python -m research.lib.tick_import "C:/Users/me/Documents/NinjaTrader 8/tickdata"

    # also build loader-compatible bar files (research/data/<SYM>_1min_fromticks.csv):
    python -m research.lib.tick_import <tickdata dir> --to-bars 1min 5min

    # ACCEPTANCE GATE — validate tick-derived 1-min bars against an NT8 chart
    # export for the same window before ever backtesting on them:
    python -m research.lib.tick_import <tickdata dir> --to-bars 1min \
        --validate research/data/MNQ_1min.csv --instrument MNQ

Validation passes when >=99% of overlapping bars match within 1 tick on every
OHLC field. Tick-derived VOLUME can legitimately differ slightly from chart
exports (feed aggregation), so volume is reported but not gated.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
OUT_DIR = ROOT / "research" / "data" / "ticks_nt8"
BARS_DIR = ROOT / "research" / "data"


def read_tick_csv(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, sep=";")
    df.columns = [c.lower().strip() for c in df.columns]
    if not {"time", "price", "volume"} <= set(df.columns):
        raise ValueError(f"{path}: expected time;price;volume header")
    df["time"] = pd.to_datetime(df["time"], format="%Y-%m-%d %H:%M:%S.%f",
                                errors="coerce")
    df["price"] = pd.to_numeric(df["price"], errors="coerce")
    df["volume"] = pd.to_numeric(df["volume"], errors="coerce").fillna(0)
    bad = df["time"].isna() | df["price"].isna() | (df["price"] <= 0)
    if bad.any():
        print(f"  [qc] {path.name}: dropped {int(bad.sum())} malformed row(s)")
    df = df[~bad].sort_values("time").reset_index(drop=True)
    return df


def import_dir(source: Path) -> list[tuple[str, Path]]:
    """Convert every <INSTRUMENT>/<day>.csv under source to parquet. Returns
    [(instrument, parquet_path)] for everything imported this run."""
    imported = []
    inst_dirs = [d for d in sorted(source.iterdir()) if d.is_dir()]
    if not inst_dirs:
        raise SystemExit(f"No instrument folders under {source} — is TickRecorder "
                         "running and writing? (see ninjascript/README.md)")
    for inst_dir in inst_dirs:
        for csv in sorted(inst_dir.glob("*.csv")):
            ticks = read_tick_csv(csv)
            if ticks.empty:
                continue
            out = OUT_DIR / inst_dir.name / (csv.stem + ".parquet")
            out.parent.mkdir(parents=True, exist_ok=True)
            ticks.to_parquet(out, index=False)
            span = (f"{ticks['time'].iloc[0]:%H:%M:%S}"
                    f"..{ticks['time'].iloc[-1]:%H:%M:%S}")
            print(f"  [ok] {inst_dir.name}/{csv.name}: {len(ticks):,} ticks  {span}")
            imported.append((inst_dir.name, out))
    return imported


def ticks_to_bars(parquets: list[Path], rule: str) -> pd.DataFrame:
    frames = [pd.read_parquet(p) for p in parquets]
    ticks = (pd.concat(frames, ignore_index=True)
             .sort_values("time").set_index("time"))
    bars = pd.DataFrame({
        "open": ticks["price"].resample(rule, label="right", closed="right").first(),
        "high": ticks["price"].resample(rule, label="right", closed="right").max(),
        "low": ticks["price"].resample(rule, label="right", closed="right").min(),
        "close": ticks["price"].resample(rule, label="right", closed="right").last(),
        "volume": ticks["volume"].resample(rule, label="right", closed="right").sum(),
    }).dropna(subset=["open"])
    return bars


def root_of(instrument_dir: str) -> str:
    return instrument_dir.split("_")[0].split(" ")[0].upper()


def validate(bars: pd.DataFrame, export_path: Path, tick_size: float) -> bool:
    from .data_loader import load_bars
    ref = load_bars(export_path)
    shared = bars.index.intersection(ref.index)
    print(f"\nValidation vs {export_path.name}: {len(shared)} overlapping bars")
    if len(shared) < 30:
        print("  FAIL — too little overlap (need 30+). Same session/date range?")
        return False
    ok = True
    worst_frac = 0.0
    for field in ["open", "high", "low", "close"]:
        d = (bars.loc[shared, field] - ref.loc[shared, field]).abs() / tick_size
        frac_off = float((d > 1.0).mean())
        worst_frac = max(worst_frac, frac_off)
        print(f"  {field:<5} mean |Δ| {d.mean():.3f} ticks   "
              f"bars >1 tick: {frac_off:.2%}")
        if frac_off > 0.01:
            ok = False
    vd = (bars.loc[shared, "volume"] - ref.loc[shared, "volume"]).abs()
    print(f"  volume mean |Δ| {vd.mean():.1f} (reported, not gated)")
    print(f"\n  {'PASS' if ok else 'FAIL'} — gate: >=99% of bars within 1 tick "
          f"on every OHLC field (worst field: {worst_frac:.2%} off)")
    if not ok:
        print("  Do NOT backtest on these bars. Check clock/session settings, "
              "data-feed differences, or gaps in the capture, then re-validate.")
    return ok


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Import TickRecorder CSVs; optionally build+validate bars.")
    ap.add_argument("source", help="TickRecorder output dir (…/tickdata)")
    ap.add_argument("--to-bars", nargs="*", default=[],
                    help="also build bar files, e.g. --to-bars 1min 5min")
    ap.add_argument("--validate",
                    help="NT8 chart export to gate the 1min bars against")
    ap.add_argument("--instrument", default=None,
                    help="instrument for tick size in validation (default: "
                         "inferred from folder name)")
    args = ap.parse_args()

    source = Path(args.source)
    if not source.is_dir():
        raise SystemExit(f"{source} is not a directory")

    print(f"Importing ticks from {source}:")
    imported = import_dir(source)
    if not imported:
        raise SystemExit("Nothing imported.")

    by_inst: dict[str, list[Path]] = {}
    for inst, path in imported:
        by_inst.setdefault(inst, []).append(path)

    all_ok = True
    for inst, paths in by_inst.items():
        for rule in args.to_bars:
            bars = ticks_to_bars(paths, rule)
            out = BARS_DIR / f"{root_of(inst)}_{rule}_fromticks.csv"
            bars.rename_axis("datetime").to_csv(out)
            print(f"\n[bars] {out.name}: {len(bars):,} {rule} bars "
                  f"({bars.index[0]} .. {bars.index[-1]})")
            if args.validate and rule == "1min":
                from .instruments import get_instrument
                sym = (args.instrument or root_of(inst)).upper()
                ts = get_instrument(sym).tick_size
                all_ok &= validate(bars, Path(args.validate), ts)

    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
