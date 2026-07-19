# Trading System — Rules for Claude

## Context

- Instruments: **NQ / MNQ** and **ES / MES** futures.
- Platform: **NinjaTrader 8** (NinjaScript / C#), running on Windows.
- Prop-firm constraints: **Apex**. Automation is banned on funded Performance
  Accounts (PAs); it is currently allowed in evaluations (reconfirm in writing
  before relying on it).
- **FlowBots (Replikanto)** copies my *lead* account to my follower accounts.
- **ALERT mode only** where funded accounts are downstream. **AUTO mode only**
  when every downstream account is sim / eval / personal. See `docs/compliance.md`.

### Point & tick values (used by the backtester — see `research/lib/instruments.py`)

| Instrument | Point value | Tick size | Tick value |
|------------|-------------|-----------|------------|
| NQ         | $20         | 0.25      | $5.00      |
| MNQ        | $2          | 0.25      | $0.50      |
| ES         | $50         | 0.25      | $12.50     |
| MES        | $5          | 0.25      | $1.25      |

Backtests **must** use the correct commission per instrument — micros have
proportionally higher costs. A strategy that clears costs on NQ can be a net
loser on MNQ.

## Non-negotiables (never change these without me saying so explicitly)

- Risk limits in `RiskGuard.cs` and strategy `MaxContracts` / `DailyLossLimit`
  are **immutable** (`readonly` constants — changing them requires editing code
  and recompiling, deliberately).
- Every backtest must report: **out-of-sample results separately**, max
  drawdown, profit factor, and trade count. **Never show me in-sample results
  alone.**
- Every strategy change bumps a **version** and gets a `docs/decisions.md` entry.
- **Flag overfitting**: if I've tested >20 variants on the same data, tell me
  the results are contaminated and suggest fresh out-of-sample data. The
  out-of-sample window is **sacred — one shot per strategy.**

## Workflow

- **Python first** (`research/lib` backtester), NinjaScript port only *after* a
  strategy survives walk-forward + out-of-sample.
- NinjaScript style: NT8 managed approach, `OnBarClose` unless specified, and
  **every entry has a stop attached before the entry order is submitted.**
- Prefer strategies whose edge has a **reason** — a "why" I can say in one
  sentence — over ones that merely score well on a backtest.

## Repo map

- `research/`   — Python strategy lab (data, notebooks, backtests, shared lib).
- `ninjascript/` — `.cs` strategies, indicators, and the `RiskGuard.cs` add-on.
- `dashboard/`  — one-file local cockpit: P&L vs day/week/month targets.
- `journal/`    — exported executions, screenshots, weekly review notes.
- `docs/`       — `strategy-registry.md` (the Strategy Knowledge Base) and
  `decisions.md` (why anything changed).
