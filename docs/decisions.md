# Decision Log

Why anything changed. Every strategy change bumps a **version** and lands a line
here (CLAUDE.md non-negotiable). Newest first.

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
