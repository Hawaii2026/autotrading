"""Parse NinjaTrader 8 execution/trade exports into the dashboard's data file.

Reads:
  - dashboard/targets.json                (your targets + account stack)
  - journal/trades/*.csv                  (NT8 Trade Performance / executions exports)

Writes:
  - dashboard/data.js                     (var DASHBOARD_DATA = {...};)

We emit a `.js` (not `.json`) so `dashboard/index.html` works when opened
straight from disk (file://) — no local server, no fetch/CORS headache.

Run after each session (or on a timer):
    python dashboard/build_data.py

The trade CSV parser is deliberately forgiving. It looks for, case-insensitively:
  account   : "Account"
  instrument: "Instrument"
  pnl       : "Profit", "PnL", "Realized profit loss", "NetProfit"
  time      : "Time", "Exit time", "Close time", "Timestamp"
  qty       : "Quantity", "Qty"  (optional)
If your export differs, tweak COLUMN_ALIASES below.
"""
from __future__ import annotations

import csv
import glob
import json
import os
from collections import defaultdict
from datetime import date, datetime, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGETS_PATH = os.path.join(ROOT, "dashboard", "targets.json")
TRADES_GLOB = os.path.join(ROOT, "journal", "trades", "*.csv")
OUT_PATH = os.path.join(ROOT, "dashboard", "data.js")

COLUMN_ALIASES = {
    "account": ["account", "account name"],
    "instrument": ["instrument", "symbol"],
    "pnl": ["profit", "pnl", "net profit", "netprofit", "realized profit loss",
            "realized pnl", "realizedprofitloss"],
    "time": ["exit time", "close time", "time", "timestamp", "exit", "date"],
    "qty": ["quantity", "qty", "contracts"],
}


def _pick(header: list[str], names: list[str]) -> str | None:
    lower = {h.lower().strip(): h for h in header}
    for n in names:
        if n in lower:
            return lower[n]
    return None


def _to_float(s: str) -> float:
    if s is None:
        return 0.0
    s = str(s).replace("$", "").replace(",", "").replace("(", "-").replace(")", "").strip()
    try:
        return float(s) if s else 0.0
    except ValueError:
        return 0.0


def load_trades() -> list[dict]:
    trades: list[dict] = []
    for path in sorted(glob.glob(TRADES_GLOB)):
        with open(path, newline="", encoding="utf-8", errors="ignore") as fh:
            reader = csv.reader(fh)
            rows = list(reader)
        if not rows:
            continue
        header = rows[0]
        col = {k: _pick(header, v) for k, v in COLUMN_ALIASES.items()}
        if not col["pnl"]:
            print(f"[skip] {os.path.basename(path)}: no P&L column found")
            continue
        idx = {k: header.index(v) for k, v in col.items() if v}
        for r in rows[1:]:
            if not r or len(r) < len(header):
                continue
            t = None
            if "time" in idx:
                t = _parse_time(r[idx["time"]])
            trades.append({
                "account": r[idx["account"]].strip() if "account" in idx else "UNKNOWN",
                "instrument": (r[idx["instrument"]].strip() if "instrument" in idx
                               else "NA"),
                "pnl": _to_float(r[idx["pnl"]]),
                "time": t,
                "qty": int(_to_float(r[idx["qty"]])) if "qty" in idx else 1,
            })
    trades = [t for t in trades if t["time"] is not None]
    trades.sort(key=lambda t: t["time"])
    return trades


def _parse_time(s: str):
    s = (s or "").strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%m/%d/%Y %H:%M:%S", "%m/%d/%Y %I:%M:%S %p",
                "%Y-%m-%d", "%m/%d/%Y", "%Y%m%d %H%M%S"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def _instrument_group(sym: str) -> str:
    s = sym.upper()
    for key in ("MNQ", "MES", "NQ", "ES"):
        if s.startswith(key):
            return key
    return s


def trading_days_elapsed(period_start: date, today: date) -> int:
    d, n = period_start, 0
    while d <= today:
        if d.weekday() < 5:
            n += 1
        d += timedelta(days=1)
    return n


def build(today: date | None = None) -> dict:
    with open(TARGETS_PATH, encoding="utf-8") as fh:
        cfg = json.load(fh)
    trades = load_trades()

    if today is None:
        today = trades[-1]["time"].date() if trades else date.today()

    week_start = today - timedelta(days=today.weekday())
    month_start = today.replace(day=1)

    def window_sum(pred) -> float:
        return round(sum(t["pnl"] for t in trades if pred(t["time"].date())), 2)

    day_pnl = window_sum(lambda d: d == today)
    week_pnl = window_sum(lambda d: d >= week_start)
    month_pnl = window_sum(lambda d: d >= month_start)

    # equity curve (cumulative net P&L across all trades, stack total)
    cum = 0.0
    equity = []
    for t in trades:
        cum += t["pnl"]
        equity.append({"t": t["time"].strftime("%Y-%m-%d %H:%M"), "y": round(cum, 2)})

    # max drawdown of that curve
    peak = float("-inf")
    max_dd = 0.0
    for pt in equity:
        peak = max(peak, pt["y"])
        max_dd = max(max_dd, peak - pt["y"])

    # per-account rollups + distance to trailing threshold
    by_account = defaultdict(lambda: {"day": 0.0, "week": 0.0, "month": 0.0,
                                      "all": 0.0, "trades": 0})
    for t in trades:
        a = by_account[t["account"]]
        d = t["time"].date()
        a["all"] += t["pnl"]
        a["trades"] += 1
        if d == today: a["day"] += t["pnl"]
        if d >= week_start: a["week"] += t["pnl"]
        if d >= month_start: a["month"] += t["pnl"]

    accounts = []
    for acc in cfg["accounts"]:
        roll = by_account.get(acc["name"], None)
        pnl_all = round(roll["all"], 2) if roll else 0.0
        trailing = acc.get("trailing_drawdown", 0)
        # crude live-ish distance to failure line using realized P&L only
        dist = round(trailing + pnl_all, 2) if trailing else None
        accounts.append({
            "name": acc["name"], "role": acc.get("role"), "kind": acc.get("kind"),
            "size": acc.get("size"), "trailing_drawdown": trailing,
            "day": round(roll["day"], 2) if roll else 0.0,
            "week": round(roll["week"], 2) if roll else 0.0,
            "month": round(roll["month"], 2) if roll else 0.0,
            "all": pnl_all,
            "trades": roll["trades"] if roll else 0,
            "distance_to_threshold": dist,
        })

    # performance rollups
    pnls = [t["pnl"] for t in trades]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]
    gross_win = sum(wins)
    gross_loss = abs(sum(losses))

    def by_group(keyfn):
        g = defaultdict(lambda: {"pnl": 0.0, "trades": 0})
        for t in trades:
            k = keyfn(t)
            g[k]["pnl"] = round(g[k]["pnl"] + t["pnl"], 2)
            g[k]["trades"] += 1
        return g

    tdays = cfg.get("trading_days_per_month", 21)
    perf = {
        "trades": len(trades),
        "win_rate": round(len(wins) / len(pnls), 4) if pnls else 0,
        "profit_factor": round(gross_win / gross_loss, 2) if gross_loss else None,
        "avg_win": round(sum(wins) / len(wins), 2) if wins else 0,
        "avg_loss": round(sum(losses) / len(losses), 2) if losses else 0,
        "by_instrument": {k: v for k, v in by_group(
            lambda t: _instrument_group(t["instrument"])).items()},
    }

    return {
        "generated": today.strftime("%Y-%m-%d"),
        "targets": cfg["targets"],
        "pace": {
            "day": {"pnl": day_pnl, "target": cfg["targets"]["daily"]},
            "week": {
                "pnl": week_pnl, "target": cfg["targets"]["weekly"],
                "days_elapsed": trading_days_elapsed(week_start, today),
                "days_total": 5,
            },
            "month": {
                "pnl": month_pnl, "target": cfg["targets"]["monthly"],
                "days_elapsed": trading_days_elapsed(month_start, today),
                "days_total": tdays,
            },
        },
        "equity": equity,
        "max_drawdown": round(max_dd, 2),
        "accounts": accounts,
        "performance": perf,
    }


def main() -> None:
    data = build()
    with open(OUT_PATH, "w", encoding="utf-8") as fh:
        fh.write("// AUTO-GENERATED by dashboard/build_data.py — do not edit.\n")
        fh.write("var DASHBOARD_DATA = ")
        json.dump(data, fh, indent=2)
        fh.write(";\n")
    print(f"Wrote {OUT_PATH}  ({data['performance']['trades']} trades)")


if __name__ == "__main__":
    main()
