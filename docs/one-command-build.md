# One-Command Build — paste into Claude Code on the Windows PC

Open a terminal in the repo folder on the trading PC, run `claude`, and paste
everything inside the box as one message. It runs the whole build, pausing only
at the three `[NEEDS ME]` points (NT8 compile, Telegram token, data export).

Two corrections are already baked into this copy (vs. the draft):

1. **`main` does not exist yet** — the repo was born on the feature branch, so
   Step 1 *creates* main from it rather than checking it out.
2. **`RiskGuard.cs` goes under `Strategies\`**, not `AddOns\` — it derives from
   `Strategy` so it can flatten the account (see `ninjascript/README.md`).

Also note: `update_dashboard.bat` already exists in the repo root — Step 5 only
needs to create the gitignored `dashboard\deploy_cmd.bat` with the deploy line.

If the session gets interrupted, paste the same prompt again and add:
*"Resume — check docs/phase1-acceptance.md and git log for what's already done,
skip completed steps."*

---

```
You are finishing the build of my lean NT8 trading system end-to-end in this one
session. The repo scaffold already exists (branch
claude/lean-ninjatrader-strategy-system-jestar). Read CLAUDE.md and
docs/compliance.md first and obey them throughout. Work through the steps below
in order, autonomously. Only stop to ask me for input at the three [NEEDS ME]
points — at each one, tell me exactly what to click or paste, wait for my
answer, verify the result, then continue on your own. At the end, print a
summary with the live dashboard URL.

GUARDRAILS (non-negotiable):
- Never modify any risk limit value in RiskGuard.cs or strategy MaxContracts /
  DailyLossLimit while fixing anything.
- .env and journal/trades/ exports must never be committed. Verify .gitignore
  covers them before every commit.
- The dashboard deployment must NOT put my tokens or account numbers in the
  repo. data.js may contain P&L; it gets uploaded directly to the host, never
  committed to git.
- ALERT/AUTO compliance rules in docs/compliance.md stay exactly as written.

STEP 1 — Create main from the scaffold branch and verify it.
The repo has NO main branch yet. Run:
  git fetch origin
  git checkout claude/lean-ninjatrader-strategy-system-jestar
  git checkout -b main
  git push -u origin main
Create/activate .venv, install requirements, run python tests/smoke_test.py.
If anything fails on Windows (path separators, encoding), fix it and re-run
until green, and commit the fixes.

STEP 2 — Install the NinjaScript files.
Copy the .cs files into Documents\NinjaTrader 8\bin\Custom\ per the destination
map in ninjascript/README.md (note: RiskGuard.cs goes under Strategies\, only
AlertSender.cs goes under AddOns\). Detect my Documents path; ask only if
ambiguous.
[NEEDS ME #1] Then tell me to open NinjaTrader 8 -> New -> NinjaScript Editor
and press F5, and to paste you the full error list if compilation fails. Fix
any compile errors I paste (API signatures, usings, namespaces — never risk
values), have me recopy/recompile, and loop until I confirm "compile
successful". Copy the corrected files back into the repo and commit.

STEP 3 — Telegram alert path.
[NEEDS ME #2] Walk me through BotFather (/newbot) and getting my chat_id via
the getUpdates URL, then have me paste the token and chat_id to you. Write them
to .env (gitignored) and wherever AlertSender.cs expects them per
docs/security.md. Send a test message to the bot via curl/PowerShell and
confirm I received it on my phone. Then tell me to add the LineCrossAlert
indicator to an MNQ chart and drag the line across price; wait for me to
confirm the phone push arrived within ~2 seconds. That is the Phase 1
acceptance gate — record it as passed in docs/phase1-acceptance.md.

STEP 4 — Real market data.
[NEEDS ME #3] Give me the exact NT8 click-path (Control Center -> Tools ->
Historical Data) to download and then export NQ and ES continuous 1-min and
5-min history, as far back as my feed allows (target 2-3 years), and tell me
exactly what filenames/locations research/data/ needs (see
research/data/README.md). When I confirm the export finished, validate with:
  python -m research.lib.loader --check research/data/
Check bar counts, date ranges, gap flags, correct tick alignment per
instrument spec. Fix loader issues if the NT8 export format differs from what
the scaffold assumed. Then lock the out-of-sample boundary: record in
docs/strategy-registry.md that data from 2025-01-01 forward is OOS and must
never be used for tuning.

STEP 5 — Dashboard live on the web.
Ask me for: my accounts (name, size, which is lead) and my daily/weekly/monthly
profit targets, and write dashboard/targets.json.
Then deploy the dashboard to a real URL. Preferred: Cloudflare Pages via
wrangler (free) — create the project, run `wrangler login` (I'll click the
browser approval), and deploy the dashboard/ folder directly with
`wrangler pages deploy` so data.js is uploaded, not committed. Put Cloudflare
Access in front of it with a one-time-PIN policy for my email if I agree
(recommended — it's my P&L on the internet; ~2 extra minutes). If Cloudflare
fails or I prefer not to, fall back to Netlify CLI, same direct-upload pattern.
update_dashboard.bat already exists in the repo root — create the gitignored
dashboard\deploy_cmd.bat containing the deploy command so the .bat redeploys
after each session's export.
Run it once end-to-end with a sample/sim export and verify the live URL renders
the tiles correctly on both desktop and phone.

STEP 6 — Wrap up.
Commit everything (verify again: no .env, no exports, no data.js, no
deploy_cmd.bat in git), push, update docs/phase1-acceptance.md with all gates
and dates, and print a final summary: what passed, the live dashboard URL, the
update_dashboard.bat usage line, and the single next action for Phase 2 (fill
in 2-3 strategy idea templates in docs/strategy-registry.md).
```
