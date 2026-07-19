#region Using declarations
using System;
using System.ComponentModel.DataAnnotations;
using NinjaTrader.Cbi;
using NinjaTrader.NinjaScript;
using NinjaTrader.Data;
using NinjaTrader.NinjaScript.DrawingTools;
using NinjaTrader.Custom.AlertUtils;
#endregion

// Opening-Range Breakout strategy — the NinjaScript port of research/backtests/orb.
// Faithful to the Python signal logic so their trade lists tell the same story:
// first N minutes set the range; the first close beyond it fires a stop/target
// bracket in that direction; one entry per side per day; no entries after a cutoff.
//
// TWO MODES (a parameter — set per instance):
//   ALERT : on setup completion -> chart marker + sound + phone push with
//           instrument/direction/entry/stop/target. NO orders are ever submitted.
//           This is the ONLY mode allowed where a funded Apex account is downstream.
//   AUTO  : submits and manages the bracket itself. Sim / Market Replay / eval /
//           personal accounts ONLY. See docs/compliance.md.
//
// CLAUDE.md rule enforced here: every entry has its stop attached BEFORE the entry
// order is submitted (SetStopLoss/SetProfitTarget are set prior to EnterLong/Short).
namespace NinjaTrader.NinjaScript.Strategies
{
    public class OpeningRangeStrategy : Strategy
    {
        public enum TradeMode { Alert, Auto }

        private double orHigh, orLow;
        private bool   orComplete;
        private bool   firedToday;
        private DateTime sessionDate = DateTime.MinValue;

        private TimeSpan sessionOpen;
        private TimeSpan orEnd;
        private TimeSpan cutoff;

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Description = "Opening-range breakout with ALERT/AUTO modes and an attached bracket.";
                Name        = "OpeningRangeStrategy";
                Calculate   = Calculate.OnBarClose;         // OnBarClose semantics (matches Python)
                EntriesPerDirection = 1;
                EntryHandling = EntryHandling.AllEntries;
                IsExitOnSessionCloseStrategy = true;        // no overnight holds
                ExitOnSessionCloseSeconds = 60;
                BarsRequiredToTrade = 20;

                // --- inputs ---
                Mode         = TradeMode.Alert;             // default to the SAFE mode
                OpenMinutes  = 15;
                StopTicks    = 40;
                RewardRisk   = 2.0;
                Contracts    = 1;
                SessionStart = "09:30";
                NoEntryAfter = "12:00";
                MaxContracts = 4;                           // strategy-level hard cap (see also RiskGuard)
                SoundFile    = @"Alert2.wav";
            }
            else if (State == State.Configure)
            {
                sessionOpen = ParseTime(SessionStart);
                orEnd       = sessionOpen + TimeSpan.FromMinutes(OpenMinutes);
                cutoff      = ParseTime(NoEntryAfter);
            }
        }

        protected override void OnBarUpdate()
        {
            if (CurrentBar < BarsRequiredToTrade)
                return;

            // guardrail: never size beyond the cap regardless of input
            int qty = Math.Min(Math.Max(Contracts, 1), MaxContracts);

            // --- session roll: reset the opening range each new day ---
            if (Time[0].Date != sessionDate)
            {
                sessionDate = Time[0].Date;
                orHigh = double.MinValue;
                orLow  = double.MaxValue;
                orComplete = false;
                firedToday = false;
            }

            var tod = Time[0].TimeOfDay;

            // --- build the opening range ---
            if (tod >= sessionOpen && tod < orEnd)
            {
                orHigh = Math.Max(orHigh, High[0]);
                orLow  = Math.Min(orLow, Low[0]);
                return;
            }
            if (tod >= orEnd && !orComplete && orHigh > double.MinValue)
            {
                orComplete = true;
                Draw.HorizontalLine(this, "orHigh", orHigh, System.Windows.Media.Brushes.DimGray);
                Draw.HorizontalLine(this, "orLow", orLow, System.Windows.Media.Brushes.DimGray);
            }

            // --- entry window checks ---
            if (!orComplete || firedToday || tod > cutoff || tod < orEnd)
                return;
            if (Position.MarketPosition != MarketPosition.Flat)
                return;

            double stopDist = StopTicks * TickSize;

            if (Close[0] > orHigh)
            {
                double entry = Close[0];
                double stop  = entry - stopDist;
                double target = entry + RewardRisk * stopDist;
                FireLong(qty, entry, stop, target);
                firedToday = true;
            }
            else if (Close[0] < orLow)
            {
                double entry = Close[0];
                double stop  = entry + stopDist;
                double target = entry - RewardRisk * stopDist;
                FireShort(qty, entry, stop, target);
                firedToday = true;
            }
        }

        // ---- ALERT vs AUTO execution -------------------------------------------

        private void FireLong(int qty, double entry, double stop, double target)
        {
            string msg = FormatSetup("LONG", entry, stop, target);
            Announce(msg, true);
            if (Mode == TradeMode.Auto)
            {
                // stop + target attached BEFORE the entry (CLAUDE.md non-negotiable)
                SetStopLoss("ORB_Long", CalculationMode.Price, stop, false);
                SetProfitTarget("ORB_Long", CalculationMode.Price, target);
                EnterLong(qty, "ORB_Long");
            }
        }

        private void FireShort(int qty, double entry, double stop, double target)
        {
            string msg = FormatSetup("SHORT", entry, stop, target);
            Announce(msg, false);
            if (Mode == TradeMode.Auto)
            {
                SetStopLoss("ORB_Short", CalculationMode.Price, stop, false);
                SetProfitTarget("ORB_Short", CalculationMode.Price, target);
                EnterShort(qty, "ORB_Short");
            }
        }

        private string FormatSetup(string dir, double entry, double stop, double target)
        {
            string modeTag = Mode == TradeMode.Alert ? "ALERT" : "AUTO";
            return $"[{modeTag}] {Instrument.MasterInstrument.Name} ORB {dir}  "
                 + $"entry {entry}  stop {stop}  target {target}  ({Time[0]:HH:mm})";
        }

        private void Announce(string msg, bool up)
        {
            Draw.TextFixed(this, "setup", msg, TextPosition.BottomRight);
            Draw.ArrowUp(this, "sig" + CurrentBar, false, 0,
                up ? Low[0] - TickSize * 4 : High[0] + TickSize * 4,
                up ? System.Windows.Media.Brushes.LimeGreen : System.Windows.Media.Brushes.Red);

            if (!string.IsNullOrWhiteSpace(SoundFile))
                Alert("orb", Priority.High, msg, SoundFile, 0,
                      System.Windows.Media.Brushes.Black,
                      up ? System.Windows.Media.Brushes.LimeGreen
                         : System.Windows.Media.Brushes.Red);

            AlertSender.Send(msg);   // phone push in BOTH modes
        }

        private static TimeSpan ParseTime(string hhmm)
        {
            var parts = hhmm.Split(':');
            return new TimeSpan(int.Parse(parts[0]), int.Parse(parts[1]), 0);
        }

        #region Properties
        [NinjaScriptProperty]
        [Display(Name = "Mode", Order = 1, GroupName = "Execution")]
        public TradeMode Mode { get; set; }

        [NinjaScriptProperty]
        [Range(1, int.MaxValue)]
        [Display(Name = "Contracts", Order = 2, GroupName = "Execution")]
        public int Contracts { get; set; }

        [NinjaScriptProperty]
        [Range(1, int.MaxValue)]
        [Display(Name = "Max contracts (hard cap)", Order = 3, GroupName = "Execution")]
        public int MaxContracts { get; set; }

        [NinjaScriptProperty]
        [Range(1, 240)]
        [Display(Name = "Opening range (min)", Order = 4, GroupName = "Parameters")]
        public int OpenMinutes { get; set; }

        [NinjaScriptProperty]
        [Range(1, int.MaxValue)]
        [Display(Name = "Stop (ticks)", Order = 5, GroupName = "Parameters")]
        public int StopTicks { get; set; }

        [NinjaScriptProperty]
        [Range(0.1, 100)]
        [Display(Name = "Reward:Risk", Order = 6, GroupName = "Parameters")]
        public double RewardRisk { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Session start (HH:mm)", Order = 7, GroupName = "Parameters")]
        public string SessionStart { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "No entry after (HH:mm)", Order = 8, GroupName = "Parameters")]
        public string NoEntryAfter { get; set; }

        [Display(Name = "Sound file", Order = 9, GroupName = "Alert")]
        public string SoundFile { get; set; }
        #endregion
    }
}
