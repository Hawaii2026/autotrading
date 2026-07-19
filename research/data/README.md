# research/data — exported bars

Drop your exported NQ / ES intraday bars here. Actual data files are
**gitignored** (they're large and private) — only this README is tracked.

## How to export from NinjaTrader 8

Two easy paths:

1. **Chart export** — open a 1-min (and a 5-min) NQ or ES chart covering the
   window you want, right-click → *Export…* → *Export historical data*. NT8
   writes a semicolon file: `yyyyMMdd HHmmss;open;high;low;close;volume`.
2. **Historical Data window** (Control Center → *Tools → Historical Data*) →
   select instrument/range → *Export*.

## Naming convention

Use `SYMBOL_TIMEFRAME.csv`, e.g.:

```
research/data/NQ_1min.csv
research/data/NQ_5min.csv
research/data/ES_1min.csv
```

The loader (`research/lib/data_loader.py`) auto-detects the NT8 semicolon
format and generic CSVs (a `datetime` column, or separate `date`/`time`), and
also reads `.parquet`. Validate everything you export:

```bash
python -m research.lib.loader --check research/data/
```

(prints bar counts, date ranges, and flags weekday gaps). Convert once for
fast reloads:

```python
from research.lib.data_loader import load_bars, save_parquet
bars = load_bars("research/data/NQ_1min.csv")
save_parquet(bars, "research/data/NQ_1min.parquet")
```

## Recommended coverage

- **In-sample**: 2023–2024 (tune here).
- **Out-of-sample**: 2025–2026 — the window nothing is ever tuned on. One shot
  per strategy. See CLAUDE.md.
