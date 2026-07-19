"""KarenBridge feed recorder — READ-ONLY market-data capture.

Polls the GET side of Karen's market-data endpoint (the only subscription
surface KarenBridge exposes — there is no WebSocket) and appends ticks to
daily parquet files under research/data/ticks/<INSTRUMENT>/<YYYY-MM-DD>.parquet.

    python -m research.lib.tick_recorder            # uses KAREN_FEED_URL from .env
    python -m research.lib.tick_recorder --url https://.../api/karen/ninjatrader/market-data

DATA GRADE — read this before using the output:
    KarenBridge's NT8 addon does LATEST-VALUE SAMPLING at ~2 ticks/sec per
    instrument; intermediate ticks and their volumes are dropped before they
    ever leave the trading PC. This capture is therefore DISPLAY-GRADE:
    good for the live dashboard quote, feed-health monitoring, and fidelity
    diagnostics (tools/check_karen_fidelity.py) — NEVER for backtesting.
    Research bars come from NT8 exports only (CLAUDE.md).

Behavior:
    - polls every --interval seconds (default 1.0; upstream is 2 Hz sampled,
      so 1 s captures essentially everything Karen has)
    - dedups by (instrument, marketTime)
    - auto-reconnects with capped exponential backoff; a dead feed never
      crashes the recorder
    - logs any data gap > 5 s to journal/feed_gaps.log
    - flushes parquet every 30 s and on shutdown (Ctrl-C safe)
    - writes dashboard/live.js (gitignored) with the latest quote for the
      local dashboard's live strip; --no-live disables

This module is read-only by design: it holds no credentials that could place
orders, and Karen's endpoint physically cannot accept them (docs/compliance.md;
live execution stays inside NT8).
"""
from __future__ import annotations

import argparse
import json
import os
import signal
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

try:
    import requests
except ImportError:
    sys.exit("pip install requests (see requirements.txt)")

ROOT = Path(__file__).resolve().parent.parent.parent
TICKS_DIR = ROOT / "research" / "data" / "ticks"
GAP_LOG = ROOT / "journal" / "feed_gaps.log"
LIVE_JS = ROOT / "dashboard" / "live.js"

GAP_SECONDS = 5.0
FLUSH_SECONDS = 30.0
BACKOFF_MAX = 30.0

TICK_COLUMNS = ["market_time", "price", "volume", "symbol", "received_at"]


def _load_env() -> None:
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())


def _safe_name(instrument: str) -> str:
    return instrument.replace(" ", "_").replace("/", "-")


class Recorder:
    def __init__(self, url: str, interval: float, write_live: bool):
        self.url = url
        self.interval = interval
        self.write_live = write_live
        self.session = requests.Session()
        # buffers[(instrument, date)] -> list of tick dicts
        self.buffers: dict[tuple[str, str], list[dict]] = {}
        self.seen: dict[str, str] = {}          # instrument -> last marketTime recorded
        self.last_tick_wall: float | None = None
        self.last_gap_logged: float = 0.0
        self.last_flush = time.monotonic()
        self.running = True
        self.total = 0

    # ---- polling ---------------------------------------------------------

    def poll_once(self) -> None:
        r = self.session.get(self.url, timeout=8)
        r.raise_for_status()
        data = r.json()
        if not data.get("ok") or not data.get("hasData") or not data.get("latest"):
            return
        latest = data["latest"]
        instrument = str(latest.get("instrument", "")).strip()
        market_time = str(latest.get("marketTime", "")).strip()
        if not instrument or not market_time:
            return

        if self.write_live:
            self._write_live(latest, data.get("feed") or {})

        if self.seen.get(instrument) == market_time:
            return                                  # same sampled tick as last poll
        self.seen[instrument] = market_time

        ts = pd.to_datetime(market_time, utc=True, errors="coerce")
        if pd.isna(ts):
            return
        day = ts.strftime("%Y-%m-%d")
        self.buffers.setdefault((instrument, day), []).append({
            "market_time": ts.isoformat(),
            "price": float(latest.get("price", float("nan"))),
            "volume": float(latest.get("volume") or 0),
            "symbol": str(latest.get("symbol", "")),
            "received_at": datetime.now(timezone.utc).isoformat(),
        })
        self.total += 1

        now = time.monotonic()
        if self.last_tick_wall is not None:
            gap = now - self.last_tick_wall
            if gap > GAP_SECONDS and now - self.last_gap_logged > GAP_SECONDS:
                self._log_gap(gap)
                self.last_gap_logged = now
        self.last_tick_wall = now

    # ---- persistence -----------------------------------------------------

    def flush(self) -> None:
        for (instrument, day), rows in list(self.buffers.items()):
            if not rows:
                continue
            out_dir = TICKS_DIR / _safe_name(instrument)
            out_dir.mkdir(parents=True, exist_ok=True)
            path = out_dir / f"{day}.parquet"
            new = pd.DataFrame(rows, columns=TICK_COLUMNS)
            try:
                if path.exists():
                    combined = pd.concat([pd.read_parquet(path), new],
                                         ignore_index=True)
                    combined = combined.drop_duplicates(subset=["market_time"],
                                                        keep="last")
                else:
                    combined = new
                tmp = path.with_suffix(".parquet.tmp")
                combined.to_parquet(tmp, index=False)
                os.replace(tmp, path)
                self.buffers[(instrument, day)] = []
            except ImportError:
                # no pyarrow: degrade to CSV rather than lose data
                csv_path = path.with_suffix(".csv")
                new.to_csv(csv_path, mode="a", index=False,
                           header=not csv_path.exists())
                self.buffers[(instrument, day)] = []
                print("[warn] pyarrow missing — writing CSV instead of parquet",
                      file=sys.stderr)
        self.last_flush = time.monotonic()

    def _write_live(self, latest: dict, feed: dict) -> None:
        payload = {
            "instrument": latest.get("instrument"),
            "symbol": latest.get("symbol"),
            "price": latest.get("price"),
            "volume": latest.get("volume"),
            "marketTime": latest.get("marketTime"),
            "receivedAt": latest.get("receivedAt"),
            "feedState": feed.get("state"),
            "writtenAt": datetime.now(timezone.utc).isoformat(),
        }
        try:
            tmp = LIVE_JS.with_suffix(".js.tmp")
            tmp.write_text("var LIVE_QUOTE = " + json.dumps(payload) + ";\n",
                           encoding="utf-8")
            os.replace(tmp, LIVE_JS)
        except OSError:
            pass  # live strip is best-effort

    def _log_gap(self, gap_seconds: float) -> None:
        GAP_LOG.parent.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with GAP_LOG.open("a", encoding="utf-8") as fh:
            fh.write(f"{stamp}  gap {gap_seconds:.1f}s without a new tick "
                     f"(url={self.url})\n")
        print(f"[gap] {gap_seconds:.1f}s without a new tick — logged", flush=True)

    # ---- main loop -------------------------------------------------------

    def run(self) -> None:
        print(f"Recording KarenBridge feed -> {TICKS_DIR}")
        print(f"  url={self.url}  interval={self.interval}s  "
              f"live_strip={'on' if self.write_live else 'off'}")
        print("  DISPLAY-GRADE data (2 Hz sampled upstream) — never backtest on it.")
        backoff = self.interval
        while self.running:
            started = time.monotonic()
            try:
                self.poll_once()
                backoff = self.interval          # healthy: reset backoff
            except Exception as exc:
                print(f"[reconnect] {type(exc).__name__}: {exc} — "
                      f"retrying in {backoff:.0f}s", flush=True)
                # a dead feed is also a gap
                now = time.monotonic()
                if (self.last_tick_wall is not None
                        and now - self.last_tick_wall > GAP_SECONDS
                        and now - self.last_gap_logged > GAP_SECONDS):
                    self._log_gap(now - self.last_tick_wall)
                    self.last_gap_logged = now
                time.sleep(backoff)
                backoff = min(backoff * 2, BACKOFF_MAX)
                continue
            if time.monotonic() - self.last_flush >= FLUSH_SECONDS:
                self.flush()
            elapsed = time.monotonic() - started
            time.sleep(max(0.0, self.interval - elapsed))
        self.flush()
        print(f"Stopped. {self.total} ticks recorded this run.")

    def stop(self, *_args) -> None:
        self.running = False


def main() -> int:
    _load_env()
    ap = argparse.ArgumentParser(description="Record the KarenBridge market feed.")
    ap.add_argument("--url", default=os.environ.get("KAREN_FEED_URL", ""),
                    help="feed GET endpoint (default: KAREN_FEED_URL from .env)")
    ap.add_argument("--interval", type=float, default=1.0,
                    help="poll interval seconds (default 1.0)")
    ap.add_argument("--no-live", action="store_true",
                    help="don't write dashboard/live.js")
    args = ap.parse_args()

    if not args.url:
        print("No feed URL. Set KAREN_FEED_URL in .env, e.g.\n"
              "  KAREN_FEED_URL=https://<your-karen>.fly.dev/api/karen/"
              "ninjatrader/market-data", file=sys.stderr)
        return 1

    rec = Recorder(args.url, args.interval, write_live=not args.no_live)
    signal.signal(signal.SIGINT, rec.stop)
    signal.signal(signal.SIGTERM, rec.stop)
    rec.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
