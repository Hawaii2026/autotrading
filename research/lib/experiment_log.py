"""Variant-contamination ledger — enforces the CLAUDE.md overfitting rule.

Every distinct parameter set evaluated against a data window is one *variant*.
Test more than ~20 variants of an idea on the same data and the best backtest
you see is selection noise, not edge. This module makes that rule a recorded
fact instead of a memory:

- ``log_variants(idea, param_sets, data_window)`` — append what a run evaluated
  to ``research/backtests/experiment_log.jsonl`` (dedup by param hash, so
  re-running the same grid doesn't inflate the count).
- ``variant_count(idea)`` / ``check_contamination(idea)`` — query the ledger;
  the check prints the CLAUDE.md warning once an idea crosses the line.

CLI:
    python -m research.lib.experiment_log --status
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path

CONTAMINATION_LIMIT = 20

LOG_PATH = (Path(__file__).resolve().parent.parent
            / "backtests" / "experiment_log.jsonl")


def _param_hash(params: dict) -> str:
    canon = json.dumps(params, sort_keys=True, default=str)
    return hashlib.sha256(canon.encode()).hexdigest()[:12]


def _read() -> list[dict]:
    if not LOG_PATH.exists():
        return []
    entries = []
    for line in LOG_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return entries


def log_variants(idea: str, param_sets: list[dict], data_window: str) -> int:
    """Record evaluated variants; returns the idea's total distinct count."""
    existing = {(e["idea"], e["hash"]) for e in _read()}
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.now().isoformat(timespec="seconds")
    with LOG_PATH.open("a", encoding="utf-8") as fh:
        for params in param_sets:
            h = _param_hash(params)
            if (idea, h) in existing:
                continue
            existing.add((idea, h))
            fh.write(json.dumps({
                "idea": idea, "hash": h, "params": params,
                "data_window": data_window, "logged": now,
            }) + "\n")
    return variant_count(idea)


def variant_count(idea: str) -> int:
    return len({e["hash"] for e in _read() if e["idea"] == idea})


def check_contamination(idea: str) -> bool:
    """Print the CLAUDE.md warning if over the line. Returns True if contaminated."""
    n = variant_count(idea)
    if n > CONTAMINATION_LIMIT:
        print(f"\n[!] OVERFITTING WARNING — '{idea}' has {n} distinct variants "
              f"tested on this data (> {CONTAMINATION_LIMIT}).")
        print("    These results are CONTAMINATED by selection: the best backtest "
              "is likely noise.")
        print("    Get fresh out-of-sample data before drawing any conclusion, "
              "and log the idea's status in docs/strategy-registry.md.")
        return True
    return False


def status() -> str:
    entries = _read()
    if not entries:
        return "Experiment log is empty — no variants recorded yet."
    lines = ["Variants tested per idea (contamination line = "
             f"{CONTAMINATION_LIMIT}):"]
    ideas = sorted({e["idea"] for e in entries})
    for idea in ideas:
        n = variant_count(idea)
        flag = "  <-- CONTAMINATED" if n > CONTAMINATION_LIMIT else ""
        lines.append(f"  {idea:<24} {n:>3}{flag}")
    return "\n".join(lines)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Variant-contamination ledger")
    ap.add_argument("--status", action="store_true", help="show per-idea counts")
    ap.parse_args()  # --status is the only (and default) action
    print(status())
