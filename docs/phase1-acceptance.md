# Phase 1 — Foundation acceptance checklist

Build the whole alert path **before any strategy exists**, then prove data loads.

## The gates (check these off, commit, and you're formally into Phase 2)

- [ ] **1. Code on machine** — repo cloned/merged; `ls` shows `research/`,
      `ninjascript/`, `dashboard/`, `docs/`, `CLAUDE.md`.
- [ ] **2. Lab runs locally** — venv + deps installed; `python tests/smoke_test.py`
      passes all checks on this PC.
- [ ] **3. C# compiles** — files copied into `Documents\NinjaTrader 8\bin\Custom\`
      (see `ninjascript/README.md` for the destination map); F5 in the NinjaScript
      Editor → "Compile successful"; strategy visible in the Strategies list.
- [ ] **4. Phone buzz** — LineCrossAlert on a chart: marker + sound + Discord
      push within ~2 s of the cross. *(The official Phase 1 gate.)*
- [ ] **5. Real data loaded** — NQ + ES 1-min/5-min exported from the **CQG**
      feed to `research/data/` (as far back as CQG actually serves — record the
      real ranges, never pad);
      `python -m research.lib.loader --check research/data/`
      reads every file, prints counts/ranges, no big gap blocks. **From this
      moment, the OOS window (default 2025-forward, adjusted to real CQG depth
      if needed) is untouchable — note it in `docs/strategy-registry.md`.**
- [ ] **6. Dashboard first light** — real accounts + targets in
      `dashboard/targets.json`; a sim execution export parsed by
      `python dashboard/build_data.py`; tiles + account table render in
      `dashboard/index.html`.

Setup details for each gate follow.

## a) Alert pipeline, end to end (Discord)

1. Create a Discord webhook: your server → the alerts channel → **Edit
   Channel → Integrations → Webhooks → New Webhook → Copy Webhook URL**. In the
   Discord mobile app, enable push notifications for that channel so alerts
   buzz your phone.
2. Put the webhook URL where each side reads it — **and nowhere else** (it's a
   secret: never in source, logs, dashboards, or commits):
   - **Python** (dashboard/tools): copy `.env.example` → `.env`, fill in
     `DISCORD_WEBHOOK_URL`.
   - **NinjaScript** (NT8): create
     `…\Documents\NinjaTrader 8\alert_config.txt` with one line:
     `DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/…`
3. Smoke-test the sender from a terminal:
   ```bash
   python tools/send_alert.py "Phase 1 test — hello from my trading PC"
   ```
   Your phone should buzz.
4. Compile `ninjascript/addons/AlertSender.cs` and
   `ninjascript/indicators/LineCrossAlert.cs` in NT8 (NinjaScript Editor →
   Compile). Add **LineCrossAlert** to an NQ chart, set a `Trigger price` just
   above current price, `Direction = CrossAbove`. When price crosses it: chart
   marker + sound + **phone push**.

✅ **Accept when:** phone buzzes within ~2 seconds of the chart condition.

## b) Data export (CQG feed)

1. Export NQ and ES 1-min (and 5-min) bars from NT8 into `research/data/`
   (see `research/data/README.md`). The feed is **CQG** — download and export
   as far back as it actually serves (often shallower than other feeds).
   Record the real ranges; if depth is short, say so and plan to source deeper
   history separately — **never pad or synthesize bars**.
2. Validate everything at once:
   ```bash
   python -m research.lib.loader --check research/data/
   ```
   It prints bar counts, date ranges, inferred timeframe, and flags weekdays with
   no bars (a handful = market holidays; big blocks = missing exports).
3. Or load and plot interactively:
   ```python
   from research.lib.data_loader import load_bars, resample
   bars = load_bars("research/data/NQ_1min.csv")
   print(bars.tail()); resample(bars, "5min").tail()
   ```

✅ **Accept when:** the checker reads both instruments cleanly and Python can
plot your NQ data.

## Plumbing smoke test (no market data or NT8 needed)

Proves the research engine itself works end to end on synthetic data:

```bash
python -m research.backtests.orb.run_orb --sample --instrument MNQ
python tests/smoke_test.py
```
