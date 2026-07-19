# Decision Log

Why anything changed. Every strategy change bumps a **version** and lands a line
here (CLAUDE.md non-negotiable). Newest first.

---

## 2026-07-19 — KarenBridge integrated as a read-only, display-grade feed

**What KarenBridge is** (from reading `Hawaii2026/karen-ambitious-ai-system`):
a generated NT8 AddOn (`KarenCloudFeed.cs`) that POSTs sanitized JSON ticks
over HTTPS to the Karen cloud deployment
(`.../api/karen/ninjatrader/market-data` on Fly.io). The envelope is
market-data only — `{symbol, instrument, price, volume, marketTimestamp,
source, account}` — with positions/orders/balances stripped by Karen's own
schema, an instrument allowlist, price-plausibility bands, and ≤30 s
freshness. The GET side of the same endpoint (the only subscription surface;
there is no WebSocket) serves the latest tick + 5s/15s/1m/5m candles.

**Two findings that shaped the integration:**
1. *Not tick-by-tick.* The addon does latest-value sampling at ~2 ticks/sec
   per instrument; intermediate ticks and their volumes never leave the
   trading PC. The feed is **display-grade**.
2. *No archive.* Karen retains a rolling ~20,000-row buffer (~2.8 h at 2/s)
   and deletes older rows. There was nothing to import.

**What we use it for** (and what we refuse to): `research/lib/tick_recorder.py`
polls the GET endpoint (1 s), appends daily parquet under
`research/data/ticks/` (gitignored), logs >5 s gaps to
`journal/feed_gaps.log`, and feeds the dashboard's local live-quote strip
(`dashboard/live.js`, gitignored). `tools/check_karen_fidelity.py` quantifies
the sampling error vs an NT8 export. **Karen data never feeds the
backtester** — bars from a 2 Hz-sampled feed have approximate OHLC and wrong
volume, and research honesty (CLAUDE.md) rules them out; NT8 exports remain
the only research data source. No orders route through Karen in either
direction — live execution stays inside NT8 per `docs/compliance.md`
(Karen's endpoint cannot carry orders anyway, by its own design).

---

## 2026-07-19 — Repo scaffold, v0

- Adopted the **lean build** (Claude Code + NinjaTrader 8) in place of the AITOS
  local-LLM / multi-tier architecture. Rationale: Claude Code does the "AI reasons
  about strategies and writes code" job from a terminal, deleting ~70% of AITOS
  (GPU box, Ollama/vLLM, LangGraph, Redis, WebSocket bridge, model router) before
  any code is written. Strategy logic runs **natively inside NT8 as compiled C#** —
  no bridge, no second process in the order path.
- Created the repo skeleton: `research/` (Python lab + shared `lib` engine),
  `ninjascript/` (strategies, indicators, `RiskGuard.cs`), `dashboard/` (one-file
  cockpit), `journal/`, `docs/`.
- Seeded `CLAUDE.md` with the non-negotiables (immutable risk limits, honest
  OOS-separate reporting, overfitting flagging, version-on-change).
- Added **ORB v0.1** as a worked example strategy in both Python
  (`research/backtests/orb/`) and NinjaScript (`OpeningRangeStrategy.cs`), plus
  `RiskGuard.cs` and the Phase-1 `LineCrossAlert.cs`.
- Established the compliance line (`docs/compliance.md`): ALERT mode only where a
  funded Apex account is downstream; AUTO mode only when every downstream account
  is sim/eval/personal.

> Template for future entries:
> `## YYYY-MM-DD — <Strategy> vX.Y — <one-line what & why>`
