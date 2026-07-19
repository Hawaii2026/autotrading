# Strategy Registry — the Strategy Knowledge Base

One table, every strategy. This file *is* the knowledge base (no database needed
at this scale). **Log the failures too** — that is your defense against re-testing
the same dead idea into the same data until it "works." A strategy is only a
*candidate* once it holds up on the sacred out-of-sample window.

## Status legend

| Status | Meaning |
|--------|---------|
| `idea` | hypothesized, not yet backtested |
| `in-sample` | tested on IS window only — **not trustworthy yet** |
| `walk-forward` | survived walk-forward re-optimisation |
| `candidate` | held up on out-of-sample (one shot) — eligible for NinjaScript port |
| `alert-live` | running in ALERT mode (sim / replay / manual) |
| `auto-sim` | running AUTO mode in Sim101 (60–90 day campaign) |
| `deployed` | passed all gates; live via the copier (see docs/compliance.md) |
| `retired` | edge decayed or never confirmed — kept here as a record |

## Registry

| Strategy | Ver | Instruments | Edge (the "why", one sentence) | Entry / Exit logic | Trades | PF | Win% | Max DD | Tested window | Status |
|----------|-----|-------------|--------------------------------|--------------------|--------|----|------|--------|---------------|--------|
| Opening-Range Breakout (ORB) | 0.1 | NQ/MNQ, ES/MES | The first 15 min set the day's range; a decisive break often initiates the directional move. | Enter on first close beyond the opening range; fixed stop (ticks) + R:R target; one entry/side/day; no entries after 12:00; flat by close. | — | — | — | — | example / not yet run on real data | `idea` |

> The ORB row is a **worked example** wired to `research/backtests/orb/`. Replace
> its metrics with real numbers once you run it on exported NQ/ES data, and add a
> new row per idea. Never leave an in-sample-only number in the PF/Win%/DD columns
> without the `in-sample` status flag.

## Out-of-sample window declaration

> Fill this in the day real data lands in `research/data/` (Phase 1, gate 5),
> then never touch it: **OOS window: `____-__-__` forward. One shot per strategy.**

## Idea intake (fill this in BEFORE any code is written)

Every new idea gets an entry below using this template — the backtest is built
from the written spec, not from a vibe. Log the kills too.

```markdown
## Idea: <name>                      Status: UNTESTED
Thesis (one sentence — the "why" someone is on the wrong side):
Instrument(s): NQ / ES        Session: e.g. 9:30–11:00 ET only
Entry trigger (mechanical, no judgment words):
Stop (attached before entry):        Target / exit:
Filters (trend, volatility, day-of-week, news):
Expected frequency: ~N trades/week   Variants budget: max 20
```

Graduation bar (to NinjaScript port): **200+ trades, PF ≳ 1.3 after costs,
tolerable drawdown, holds up on the one-shot OOS window.** In-sample first
(2023–2024); expect most ideas to die — each honest kill is the system working.
