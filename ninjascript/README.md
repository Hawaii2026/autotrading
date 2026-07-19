# Installing the NinjaScript files in NT8

NT8 compiles custom code from `Documents\NinjaTrader 8\bin\Custom\`. Copy each
file from this repo into the folder NT8 expects:

| Repo file | Destination under `bin\Custom\` |
|---|---|
| `strategies/OpeningRangeStrategy.cs` | `Strategies\` |
| `indicators/LineCrossAlert.cs` | `Indicators\` |
| `addons/RiskGuard.cs` | `Strategies\` * |
| `addons/AlertSender.cs` | `AddOns\` |

\* `RiskGuard` derives from `Strategy` (so it can flatten the account), so NT8
wants it under `Strategies\` even though it lives in `addons/` here — it will
appear in the Strategies list, which is how you attach it to the lead account.

Then: Control Center → **New → NinjaScript Editor** → **F5** (compile).

## First-compile expectations

One or two errors on first compile are normal (a using directive, an API
signature that shifted between NT8 builds). Paste the **verbatim error list**
into Claude Code and fix iteratively. Two rules while fixing:

- **Never edit the risk-limit constants** (`DAILY_LOSS_LIMIT`, `MAX_CONTRACTS`,
  buffers) as part of a compile fix — they are immutable by design (CLAUDE.md).
- Keep the ALERT/AUTO behavior intact: no code path may submit an order in
  `Alert` mode.

## After it compiles

- **LineCrossAlert** → add to any chart (Indicators dialog) for the Phase 1
  phone-buzz gate.
- **OpeningRangeStrategy** → appears in the Strategies dialog; leave
  `Mode = Alert` (the default) anywhere a funded account is downstream — see
  `docs/compliance.md`.
- **RiskGuard** → attach to a chart of the **lead** account before any AUTO
  trading (Phase 4 gate).
- **AlertSender** credentials: Windows env vars `TELEGRAM_BOT_TOKEN` /
  `TELEGRAM_CHAT_ID`, or `Documents\NinjaTrader 8\alert_config.txt` with
  `KEY=value` lines. Never hard-code the token in the .cs files.

## Keeping repo and NT8 in sync

Edit in the repo, copy to `bin\Custom\`, recompile — or edit in the NinjaScript
Editor and copy back. Either way the repo copy is the source of truth; commit
every change that survives a compile + test.
