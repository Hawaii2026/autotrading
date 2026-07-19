# Phase 1 — Foundation acceptance checklist

Build the whole alert path **before any strategy exists**, then prove data loads.

## a) Alert pipeline, end to end

1. Create a Telegram bot with **@BotFather**; copy the token. Message the bot once,
   then read your `chat_id` from
   `https://api.telegram.org/bot<TOKEN>/getUpdates`.
2. Put the token + chat id where each side reads them:
   - **Python** (dashboard/tools): copy `.env.example` → `.env`, fill it in.
   - **NinjaScript** (NT8): set Windows env vars `TELEGRAM_BOT_TOKEN` /
     `TELEGRAM_CHAT_ID`, **or** create
     `…\Documents\NinjaTrader 8\alert_config.txt` with `KEY=value` lines.
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

## b) Data export

1. Export 2–3 years of NQ and ES 1-min (and 5-min) bars from NT8 into
   `research/data/` (see `research/data/README.md`).
2. Load and plot in Python:
   ```python
   from research.lib.data_loader import load_bars, resample
   bars = load_bars("research/data/NQ_1min.csv")
   print(bars.tail()); resample(bars, "5min").tail()
   ```

✅ **Accept when:** Python loads and plots your NQ data cleanly.

## Plumbing smoke test (no market data or NT8 needed)

Proves the research engine itself works end to end on synthetic data:

```bash
python -m research.backtests.orb.run_orb --sample --instrument MNQ
python tests/smoke_test.py
```
