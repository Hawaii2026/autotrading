# research/data/ticks — KarenBridge feed capture (DISPLAY-GRADE)

Daily files written by `research/lib/tick_recorder.py`, one folder per
instrument, one parquet per day:

```
research/data/ticks/MNQ_09-26/2026-07-21.parquet
    columns: market_time (UTC ISO), price, volume, symbol, received_at
```

## ⚠️ Not research data

KarenBridge's NT8 addon does **latest-value sampling at ~2 ticks/sec per
instrument** — intermediate ticks and their true volumes are dropped on the
trading PC before they ever reach Karen. Bars derived from these files have
approximate OHLC and wrong volume.

**Never feed this into the backtester.** Research bars come from NT8 exports
(`research/data/*.csv`) only. Use these captures for:

- the dashboard's live quote strip (`dashboard/live.js`)
- feed-health monitoring (`journal/feed_gaps.log`)
- quantifying the sampling error vs a real NT8 export:
  `python tools/check_karen_fidelity.py <day parquet> <NT8 1min csv> --instrument MNQ`

All files here are gitignored, like every other market-data file in the repo.
