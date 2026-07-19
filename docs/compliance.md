# Compliance — the ALERT / AUTO line (read before deploying)

> Not legal advice. Reconfirm every firm rule in writing with Apex before relying
> on it; policies change. This file records the rules the system is built around.

## The one rule that shapes everything

**Apex's automation ban attaches to the funded Performance Account (PA) no matter
how the order arrives.** If a bot originates a trade and a copier relays it into a
funded PA, that PA is being traded by automation — the copier does not change what
surveillance sees (machine-regular order timing across the whole stack,
simultaneously). Payout-denial risk on every account at once.

So there are exactly two legal shapes:

## Setup A — Funded stack (the money-making config)

```
Strategy in ALERT mode ─▶ phone/screen alert ─▶ YOU click the trade on the
lead account ─▶ FlowBots mirrors to your funded PAs + evals
```

- The AI does everything **except the click**: watches the market, fires the alert
  (entry/stop/target), tracks risk, journals the result.
- **You** are the originator; the copier multiplies a *manual* trade. Standard,
  widely-used Apex multi-account workflow — one click, many accounts.
- **`OpeningRangeStrategy.Mode` MUST be `Alert`** on any chart whose lead account
  copies into a funded PA.

## Setup B — Automation stack (proving ground, zero compliance exposure)

```
Strategy in AUTO mode ─▶ fires on Sim101 lead ─▶ FlowBots mirrors to followers
that are ONLY sim / eval / personal accounts
```

- Use it to battle-test the full pipeline (AUTO strategy, copier latency,
  RiskGuard, dashboard) for the 60–90 day sim campaign, and — after reconfirming
  Apex's eval-automation policy **in writing** — to drive evaluation accounts.
- Routed into a live **personal** brokerage account, there is no restriction.

## Copier operational notes (FlowBots / Replikanto)

- Apex permits copy trading **across your own accounts** (currently up to ~20
  funded PAs), with the hard rule that **all your accounts stay on the same side
  of the market** — never manually trade a follower against the lead.
- Attach **`RiskGuard`** to the **lead** account — flattening the lead flattens
  the stack.
- Size followers per `dashboard/targets.json` (`max_contracts` per account);
  smaller accounts can take micros (2–3 MNQ) instead of 1 NQ if the copier
  supports instrument/ratio mapping.
- **Test bracket mirroring in sim first.** Mirrored stops/targets are exactly
  where copiers historically misbehave. Verify follower reject / partial-fill
  behavior before trusting real money.

## The multiplier caution

The copier multiplies **whatever the lead does — profits and mistakes alike**. A
$300 loss on one account is $6,000 across twenty. The Phase 2–5 validation gates
matter *more* with a copier, not less, because you've removed the ability to lose
small.
