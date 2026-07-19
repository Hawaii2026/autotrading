# Minimal Security — the honest floor

Everything runs locally on your own PC and connects **outbound only**, so the
security surface is naturally tiny. The realistic minimum:

1. **No inbound ports.** Nothing here listens on the network. NT8 connects out to
   your data feed (CQG); the alert sender connects out to Discord. Default
   firewall is fine.
2. **One `.env` file** for the Discord webhook URL, excluded from git via
   `.gitignore`. On Windows, the NinjaScript side reads the same secret from
   environment variables or `…\Documents\NinjaTrader 8\alert_config.txt` (see
   `ninjascript/addons/AlertSender.cs`). That is the only secret in the system.
3. **Private GitHub repo.** Your strategies are your edge — don't publish them.
4. **Hard-coded risk limits in C# marked `const` / `readonly`** — not security
   against attackers, but against your own (and AI-generated) code doing something
   dumb. This is the one item you must **not** minimize; it is real risk control.
   See `ninjascript/addons/RiskGuard.cs` and the `MaxContracts` caps in the
   strategy.

Deliberately **skipped** (they belonged to AITOS's dozen networked services, which
this build does not have): RBAC, signed inter-service messages, encrypted secret
vaults, audit infrastructure. You have zero networked services.
