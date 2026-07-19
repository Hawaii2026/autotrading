"""Load NQ/ES intraday bars exported from NinjaTrader 8 into clean DataFrames.

NT8 has a few export shapes depending on how you export. This loader is
deliberately forgiving and normalises everything to a single tz-naive
DatetimeIndex with float OHLCV columns:

    index:   datetime  (bar timestamp)
    columns: open, high, low, close, volume

Supported inputs
----------------
1. NT8 "Export" from a chart / historical data window — semicolon-separated,
   no header:  ``yyyyMMdd HHmmss;open;high;low;close;volume``
2. Generic CSV with a header containing date/time + OHLC(V) columns (any case).
3. Parquet written by this module's ``save_parquet`` (fast reloads).
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

_OHLCV = ["open", "high", "low", "close", "volume"]


def _finalize(df: pd.DataFrame) -> pd.DataFrame:
    df = df[~df.index.duplicated(keep="last")].sort_index()
    for col in _OHLCV:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    if "volume" not in df.columns:
        df["volume"] = 0.0
    df = df.dropna(subset=["open", "high", "low", "close"])
    return df[_OHLCV]


def _load_nt8_semicolon(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, sep=";", header=None,
                     names=["ts", "open", "high", "low", "close", "volume"])
    df.index = pd.to_datetime(df["ts"], format="%Y%m%d %H%M%S", errors="coerce")
    df = df.drop(columns=["ts"])
    return _finalize(df)


def _load_generic_csv(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    cols = {c.lower().strip(): c for c in df.columns}

    # Build a datetime index from either a single datetime col or date + time.
    if "datetime" in cols:
        idx = pd.to_datetime(df[cols["datetime"]], errors="coerce")
    elif "date" in cols and "time" in cols:
        idx = pd.to_datetime(
            df[cols["date"]].astype(str) + " " + df[cols["time"]].astype(str),
            errors="coerce",
        )
    elif "date" in cols:
        idx = pd.to_datetime(df[cols["date"]], errors="coerce")
    elif "timestamp" in cols:
        idx = pd.to_datetime(df[cols["timestamp"]], errors="coerce")
    else:
        raise ValueError(
            f"{path.name}: could not find a datetime column. "
            f"Columns seen: {list(df.columns)}"
        )

    out = pd.DataFrame(index=idx)
    for name in _OHLCV:
        if name in cols:
            out[name] = df[cols[name]].values
    missing = [c for c in ["open", "high", "low", "close"] if c not in out.columns]
    if missing:
        raise ValueError(f"{path.name}: missing OHLC columns {missing}")
    return _finalize(out)


def load_bars(path: str | Path) -> pd.DataFrame:
    """Load one bar file, auto-detecting the format from extension/content."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(
            f"{path} not found. Export NQ/ES bars from NT8 into research/data/ "
            "(see research/data/README.md)."
        )
    if path.suffix.lower() == ".parquet":
        return _finalize(pd.read_parquet(path))

    # Peek at the first line to decide between NT8-semicolon and generic CSV.
    with path.open("r", encoding="utf-8", errors="ignore") as fh:
        first = fh.readline()
    if ";" in first and "," not in first:
        return _load_nt8_semicolon(path)
    return _load_generic_csv(path)


def resample(df: pd.DataFrame, rule: str) -> pd.DataFrame:
    """Resample 1-min bars to a coarser timeframe, e.g. resample(df, '5min')."""
    agg = {"open": "first", "high": "max", "low": "min",
           "close": "last", "volume": "sum"}
    return df.resample(rule, label="right", closed="right").agg(agg).dropna()


def save_parquet(df: pd.DataFrame, path: str | Path) -> None:
    """Persist a cleaned frame for fast reloads (needs pyarrow)."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path)
