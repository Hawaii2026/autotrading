#region Using declarations
using System;
using System.Collections.Generic;
using System.ComponentModel.DataAnnotations;
using System.Linq;
using NinjaTrader.Cbi;
using NinjaTrader.NinjaScript;
using NinjaTrader.Custom.AlertUtils;
#endregion

// Account-level flatten guard. Attach it to a chart of the LEAD account you trade
// (flattening the lead flattens the FlowBots stack). It watches the account and,
// on any breach, flattens everything, cancels working orders, and locks out new
// entries for the rest of the session.
//
// DESIGN INTENT — the hard limits below are `const` / `readonly` ON PURPOSE. They
// are NOT exposed as editable strategy inputs. Changing a limit requires editing
// this file and recompiling. That friction is the point: it protects you (and any
// AI-generated strategy code) from a bad day, an oversize fat-finger, or a runaway
// loop. See docs/security.md and CLAUDE.md ("Non-negotiables").
//
// It appears under Strategies in NT8 (it derives from Strategy so it can flatten).
namespace NinjaTrader.NinjaScript.Strategies
{
    public class RiskGuard : Strategy
    {
        // ================= IMMUTABLE HARD LIMITS (edit + recompile to change) ====
        private const double DAILY_LOSS_LIMIT   = 1000.0;  // $ realized loss/session -> lockout
        private const int    MAX_CONTRACTS      = 4;       // reject/flatten if net position exceeds
        private const double TRAIL_BUFFER_NQ    = 300.0;   // $ buffer above trailing threshold (NQ)
        private const int    NO_ENTRY_OPEN_MIN  = 1;       // no entries in first N min of session
        private const int    NO_ENTRY_CLOSE_MIN = 5;       // flatten in last N min before close
        // =========================================================================

        private bool     lockedOut;
        private double   peakEquity;
        private DateTime sessionDate = DateTime.MinValue;
        private readonly TimeSpan sessionOpen  = new TimeSpan(9, 30, 0);   // ET, adjust to your chart TZ
        private readonly TimeSpan sessionClose = new TimeSpan(16, 0, 0);
        private List<(DateTime start, DateTime end)> newsBlackouts = new List<(DateTime, DateTime)>();

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Description  = "Account flatten guard: trailing-drawdown buffer, daily loss stop, "
                             + "max contracts, time & news filters. Hard limits are immutable.";
                Name         = "RiskGuard";
                Calculate    = Calculate.OnEachTick;   // react fast, not just on bar close
                IsOverlay    = true;
                IsUnmanaged  = false;
                EntriesPerDirection = 1;

                // Per-account input: the firm's trailing drawdown amount for THIS account
                // (e.g. $2,500 on a 50K Apex account). Buffer/limits above stay immutable.
                TrailingDrawdown = 2500.0;
                PointValueBuffer = TRAIL_BUFFER_NQ;   // $ buffer; scales per instrument point value
                EnableNewsBlackout = true;
            }
            else if (State == State.Configure)
            {
                LoadNewsCalendar();
            }
        }

        protected override void OnBarUpdate()
        {
            // day roll: reset lockout + peak equity at the start of each session
            if (Time[0].Date != sessionDate)
            {
                sessionDate = Time[0].Date;
                lockedOut = false;
                peakEquity = AccountEquity();
                LoadNewsCalendar();
            }

            if (lockedOut)
                return;

            CheckMaxContracts();
            CheckDailyLoss();
            CheckTrailingBuffer();
            CheckTimeAndNewsFilters();
        }

        // ---- individual guards ---------------------------------------------------

        private void CheckMaxContracts()
        {
            int net = Math.Abs(Position.Quantity);
            if (net > MAX_CONTRACTS)
                Trip($"Max contracts exceeded ({net} > {MAX_CONTRACTS})");
        }

        private void CheckDailyLoss()
        {
            double realized = Account.Get(AccountItem.RealizedProfitLoss, Currency.UsDollar);
            if (realized <= -DAILY_LOSS_LIMIT)
                Trip($"Daily loss limit hit (realized {realized:C0} <= -{DAILY_LOSS_LIMIT:C0})");
        }

        private void CheckTrailingBuffer()
        {
            double equity = AccountEquity();
            if (equity > peakEquity)
                peakEquity = equity;                       // track highest UNREALIZED equity

            double threshold = peakEquity - TrailingDrawdown;   // firm's trailing failure line
            double buffer = InstrumentBuffer();                 // scaled per point value
            if (equity - threshold <= buffer)
                Trip($"Trailing buffer breached: equity {equity:C0} within {buffer:C0} "
                   + $"of threshold {threshold:C0}");
        }

        private void CheckTimeAndNewsFilters()
        {
            var t = Time[0].TimeOfDay;

            // flatten before the close
            if (t >= sessionClose - TimeSpan.FromMinutes(NO_ENTRY_CLOSE_MIN))
            {
                if (Position.MarketPosition != MarketPosition.Flat)
                    FlattenEverything("Pre-close flatten");
                return;
            }

            // news blackout: flatten + lock during scheduled high-impact windows
            if (EnableNewsBlackout)
            {
                foreach (var (start, end) in newsBlackouts)
                {
                    if (Time[0] >= start && Time[0] <= end)
                    {
                        Trip($"News blackout {start:HH:mm}-{end:HH:mm}");
                        return;
                    }
                }
            }
        }

        // ---- helpers -------------------------------------------------------------

        private double AccountEquity()
        {
            // realized cash P&L + open unrealized = live equity
            double cash = Account.Get(AccountItem.CashValue, Currency.UsDollar);
            double unrealized = Account.Get(AccountItem.UnrealizedProfitLoss, Currency.UsDollar);
            return cash + unrealized;
        }

        private double InstrumentBuffer()
        {
            // Buffer is expressed for NQ; scale by this instrument's point value so a
            // micro gets a proportionally smaller $ buffer (CLAUDE.md sizing note).
            double pv = Instrument != null && Instrument.MasterInstrument != null
                ? Instrument.MasterInstrument.PointValue : 20.0;
            return PointValueBuffer * (pv / 20.0);   // 20 = NQ point value reference
        }

        private void Trip(string reason)
        {
            lockedOut = true;
            FlattenEverything(reason);
        }

        private void FlattenEverything(string reason)
        {
            try
            {
                // cancel any working orders on this account, then flatten all positions
                foreach (var o in Account.Orders.ToList())
                    if (o.OrderState == OrderState.Working || o.OrderState == OrderState.Accepted)
                        Account.Cancel(new[] { o });

                var instruments = Account.Positions
                    .Where(p => p.MarketPosition != MarketPosition.Flat)
                    .Select(p => p.Instrument)
                    .Distinct()
                    .ToArray();
                if (instruments.Length > 0)
                    Account.Flatten(instruments);
            }
            catch (Exception ex)
            {
                Print($"RiskGuard flatten error: {ex.Message}");
            }

            string msg = $"⛔ RISKGUARD TRIPPED [{Account.Name}]: {reason}. "
                       + "Flattened + locked out for the session.";
            Print(msg);
            Log(msg, LogLevel.Warning);
            AlertSender.Send(msg);
        }

        private void LoadNewsCalendar()
        {
            // Maintain a weekly plain-text calendar of high-impact events, one per line:
            //   2026-07-30 14:00  2026-07-30 14:05   FOMC
            // stored at <MyDocuments>\NinjaTrader 8\news_calendar.txt (local chart time).
            newsBlackouts = new List<(DateTime, DateTime)>();
            try
            {
                var path = System.IO.Path.Combine(
                    Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments),
                    "NinjaTrader 8", "news_calendar.txt");
                if (!System.IO.File.Exists(path)) return;

                foreach (var raw in System.IO.File.ReadAllLines(path))
                {
                    var line = raw.Trim();
                    if (line.Length == 0 || line.StartsWith("#")) continue;
                    var parts = line.Split(new[] { "  " }, StringSplitOptions.RemoveEmptyEntries);
                    if (parts.Length < 2) continue;
                    if (DateTime.TryParse(parts[0].Trim(), out var start) &&
                        DateTime.TryParse(parts[1].Trim(), out var end))
                        newsBlackouts.Add((start, end));
                }
            }
            catch { /* calendar is optional */ }
        }

        #region Properties (per-account inputs only — hard limits are const, above)
        [NinjaScriptProperty]
        [Display(Name = "Trailing drawdown ($)", Order = 1, GroupName = "Account")]
        public double TrailingDrawdown { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Trailing buffer $ (NQ ref)", Order = 2, GroupName = "Account")]
        public double PointValueBuffer { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Enable news blackout", Order = 3, GroupName = "Filters")]
        public bool EnableNewsBlackout { get; set; }
        #endregion
    }
}
