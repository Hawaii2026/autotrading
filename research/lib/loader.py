"""Alias so the operator checklist's command works verbatim:

    python -m research.lib.loader --check research/data/

The real implementation lives in research/lib/data_loader.py.
"""
from .data_loader import (  # noqa: F401
    load_bars, main, resample, save_parquet,
)

if __name__ == "__main__":
    raise SystemExit(main())
