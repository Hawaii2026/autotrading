# AI-Assisted Strategy System — Claude Code + NinjaTrader 8

A lean, single-PC system that helps you **develop a validated strategy**, **alerts
you** when its setup appears live, and can **automate execution** in NinjaTrader —
with FlowBots replicating your lead account across your stack, and a dashboard
tracking results against your profit targets.

Everything runs locally and connects outbound only. The strategy logic lives
natively inside NT8 as compiled C# (NinjaScript) — no bridge, no localhost server,
no second process in the order path. See `docs/` and the build plan for the full
rationale (this replaces the AITOS local-LLM, multi-tier architecture).

## Two operating modes

| Mode | What it does | Where it's allowed |
|------|--------------|--------------------|
| **ALERT** | Watches live data; fires chart marker + sound + phone push with entry/stop/target. **No orders.** You click; FlowBots mirrors the manual trade. | The **only** mode where a funded Apex account is downstream. |
| **AUTO** | Submits and manages the bracket itself. | Sim / Market Replay / eval / personal accounts only. |

See **`docs/compliance.md`** — this line is load-bearing.

## Layout

```
CLAUDE.md            project rules Claude Code reads every session
research/            Python strategy lab
  lib/               shared engine: backtester, walk-forward, metrics, instruments
  backtests/orb/     worked example: Opening-Range Breakout (IS / OOS / walk-forward)
  data/              exported NQ/ES bars (gitignored)
ninjascript/
  indicators/        LineCrossAlert.cs   (Phase 1 alert-path proof)
  strategies/        OpeningRangeStrategy.cs   (ALERT/AUTO port of the ORB idea)
  addons/            RiskGuard.cs (account flatten guard), AlertSender.cs (phone push)
dashboard/           one-file local cockpit: P&L vs day/week/month targets
  index.html         open from disk — no server
  targets.json       your targets + account stack
  build_data.py      NT8 execution exports -> dashboard/data.js
journal/             exported executions, screenshots, weekly review notes
docs/                compliance, security, strategy-registry, decisions, acceptance,
                     one-command-build.md (paste-into-Claude-Code build runner)
tools/               send_alert.py (phone push), compare_trades.py (Phase 3
                     Python-vs-NT8 port fidelity check), check_karen_fidelity.py
                     (KarenBridge feed vs NT8 bars diagnostic)
tests/               smoke_test.py (engine plumbing check, no market data)
update_dashboard.bat post-session: rebuild dashboard data + redeploy (Windows)
start_recorder.bat   record the KarenBridge live feed (read-only, display-grade;
                     powers the dashboard live strip — never backtest data)
```

Guardrail tooling: `python -m research.lib.loader --check research/data/`
validates exports; `python -m research.lib.experiment_log --status` shows how
many variants each idea has burned against the 20-variant contamination line
(real backtest runs log themselves automatically).

## Quick start

```bash
python -m venv .venv && . .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                              # fill in your Discord webhook URL

# Prove the engine works end-to-end on synthetic data (no data/NT8 needed):
python tests/smoke_test.py
python -m research.backtests.orb.run_orb --sample --instrument MNQ
```

Then work through the phased build (build plan §5). Phase 1 acceptance:
`docs/phase1-acceptance.md`.

## The one rule you must not minimize

Risk limits in `ninjascript/addons/RiskGuard.cs` and the strategy's `MaxContracts`
are **immutable `const` / `readonly`** — changing them requires editing code and
recompiling, on purpose. With a copier multiplying every trade across ~20 accounts,
the validation gates matter *more*, not less. See `CLAUDE.md` and `docs/security.md`.

*Not financial advice; futures trading carries substantial risk of loss.*
