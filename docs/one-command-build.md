# One-Command Build — paste into Claude Code on the Windows PC

**Rev. 3 — CQG data feed, Discord-only alerts.** Open a terminal in an **empty
folder** on the trading PC (or in an existing clone), run `claude`, and paste
everything inside the box as one message. It runs the whole build, pausing only
at the moments that need your hands.

Baked-in facts (so the run never fights the repo):

1. Repo: `https://github.com/Hawaii2026/autotrading.git`, branch
   `claude/lean-ninjatrader-strategy-system-jestar`. **`main` may not exist
   yet** — Step 1 creates it from the branch if missing.
2. **`RiskGuard.cs` installs under `Strategies\`**, not `AddOns\` (it derives
   from `Strategy`; see `ninjascript/README.md`).
3. **Data feed is CQG** (not Rithmic/Kinetick). Historical depth is whatever
   CQG actually serves — report real ranges, never invent missing data.
4. **Alerts are Discord webhooks.** No Telegram, no BotFather, no bot tokens.
5. `update_dashboard.bat` already exists — Step 5 only creates the gitignored
   `dashboard\deploy_cmd.bat`.

If the session gets interrupted, paste the same prompt again and add:
*"Resume — check docs/phase1-acceptance.md and git log for what's already done,
skip completed steps."*

---

```
You are finishing the build of my lean NT8 trading system end-to-end in this one
session. This is a standalone project — do not access or modify any other
project on this machine (including anything named Karen) or my existing
NinjaTrader strategies and workspaces. Read CLAUDE.md and docs/compliance.md
first and obey them throughout. Work through the steps in order, autonomously.
Pause ONLY when I must: authenticate GitHub, compile NinjaScript, provide the
Discord webhook, approve a browser login, confirm an alert arrived, or export
NinjaTrader data. At each pause give me ONE short exact instruction, wait,
verify the result, then continue. At the end, print a summary with the live
dashboard URL.

GUARDRAILS (non-negotiable):
- Never modify any risk limit value in RiskGuard.cs or strategy MaxContracts /
  DailyLossLimit while fixing anything. Never enable live trading or place any
  order.
- .env and journal/trades/ exports must never be committed. Verify .gitignore
  covers them before every commit.
- The Discord webhook URL is a secret: it lives ONLY in the gitignored .env and
  in Documents\NinjaTrader 8\alert_config.txt. Never echo it into source code,
  logs, dashboard files, commits, or GitHub. Mask it if you must reference it.
- The dashboard deployment must NOT put secrets or account numbers in the repo.
  data.js may contain P&L; it is uploaded directly to the host, never committed.
- ALERT/AUTO compliance rules in docs/compliance.md stay exactly as written.

STEP 0 — Get the code (skip what's already done).
Verify the current folder: if it is empty, clone
https://github.com/Hawaii2026/autotrading.git into it ([PAUSE] if GitHub
authentication is needed: tell me exactly what to click/paste). Then:
  git fetch origin
  git checkout claude/lean-ninjatrader-strategy-system-jestar
If the folder already contains this repo, just fetch and check out the branch.

STEP 1 — Create main and verify the lab.
If origin has no main branch:
  git checkout -b main && git push -u origin main
Create/activate .venv, install requirements, run python tests/smoke_test.py.
If anything fails on Windows (path separators, encoding), fix it, re-run until
green, and commit the fixes.

STEP 2 — Install the NinjaScript files.
Copy the .cs files into Documents\NinjaTrader 8\bin\Custom\ per the destination
map in ninjascript/README.md (RiskGuard.cs -> Strategies\; AlertSender.cs and
TickRecorder.cs -> AddOns\; LineCrossAlert.cs -> Indicators\;
OpeningRangeStrategy.cs -> Strategies\). Detect my Documents path; ask only if
ambiguous. Do not touch any strategy or workspace file that is already in my
NinjaTrader installation.
[PAUSE] Tell me: "Open NinjaTrader -> New -> NinjaScript Editor -> press F5.
Reply 'compile successful' or paste the full error list." Fix any errors I
paste (API signatures, usings, namespaces — never risk values), have me
recopy/recompile, loop until I confirm success. Copy corrected files back into
the repo and commit.

STEP 3 — Discord alert path.
[PAUSE] Tell me: "In Discord: your server -> the alerts channel -> Edit
Channel -> Integrations -> Webhooks -> New Webhook -> Copy Webhook URL. Also
enable mobile push notifications for that channel in the Discord app. Paste
the webhook URL here."
When I paste it: write it to .env (DISCORD_WEBHOOK_URL=..., ALERT_CHANNEL=
discord) and to Documents\NinjaTrader 8\alert_config.txt
(DISCORD_WEBHOOK_URL=...). Confirm both files are outside git (git status must
not list .env; alert_config.txt is outside the repo entirely). Then send a test
message with python tools/send_alert.py "Alert path test".
[PAUSE] Ask me to confirm the message appeared in Discord AND my phone buzzed.
Then have me add the LineCrossAlert indicator to an MNQ chart and drag the
trigger line across price.
[PAUSE] Wait for my confirmation that the Discord push arrived within ~2
seconds of the cross. That is the Phase 1 acceptance gate — record it as
passed in docs/phase1-acceptance.md.

STEP 4 — Real market data (CQG).
My NT8 connects through CQG. CQG's intraday history is typically shallower
than other feeds — work with what it actually provides:
[PAUSE] Give me the exact click-path (Control Center -> Tools -> Historical
Data -> select NQ ##-## / ES ##-## -> Load minute data as far back as CQG
serves -> Export), the target filenames research/data/ expects (see
research/data/README.md), and wait for my "export done".
Then validate: python -m research.lib.loader --check research/data/
Report the REAL available date ranges per instrument — bar counts, first/last
date, gap flags. Never fabricate or extrapolate data that CQG did not provide.
If depth is under ~2 years, say so plainly and note that deeper history can be
sourced separately later; do not pad or synthesize.
Then lock the out-of-sample boundary in docs/strategy-registry.md based on the
data we actually have (default: 2025-01-01 forward is OOS, never used for
tuning; if CQG depth forces a different split, propose one and ask me to
approve it).

STEP 5 — Dashboard live on the web.
Ask me for: my accounts (name, size, which is lead) and daily/weekly/monthly
profit targets; write dashboard/targets.json.
Deploy the dashboard to a real URL. Preferred: Cloudflare Pages via wrangler
(free) — create the project, [PAUSE] run wrangler login and tell me exactly
what to approve in the browser, then deploy the dashboard/ folder directly
with wrangler pages deploy so data.js is uploaded, not committed. Offer
Cloudflare Access with a one-time-PIN policy for my email (recommended — it is
my P&L on the internet). Fall back to Netlify CLI on failure, same
direct-upload pattern. Create the gitignored dashboard\deploy_cmd.bat with the
deploy command so update_dashboard.bat redeploys after each session.
Run it once end-to-end with a sim export and verify the live URL renders on
desktop and phone.

STEP 6 — Wrap up.
Commit everything (verify again: no .env, no exports, no data.js, no
deploy_cmd.bat, no webhook string anywhere in the diff), push, update
docs/phase1-acceptance.md with all gates and dates, and print a final summary:
what passed, the live dashboard URL, the update_dashboard.bat usage line, and
the single next action for Phase 2 (fill in 2-3 strategy idea templates in
docs/strategy-registry.md).
```
