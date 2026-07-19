"""Shared strategy-research library: backtest engine, walk-forward, metrics.

Import the pieces you need, e.g.:

    from research.lib.data_loader import load_bars, resample
    from research.lib.backtester import backtest
    from research.lib.metrics import compute_metrics, equity_curve
    from research.lib.walk_forward import walk_forward, report
    from research.lib.instruments import get_instrument
"""
from .backtester import backtest
from .data_loader import load_bars, resample, save_parquet
from .instruments import INSTRUMENTS, get_instrument
from .metrics import compute_metrics, equity_curve
from .walk_forward import make_windows, report, walk_forward

__all__ = [
    "backtest",
    "load_bars", "resample", "save_parquet",
    "INSTRUMENTS", "get_instrument",
    "compute_metrics", "equity_curve",
    "make_windows", "report", "walk_forward",
]
