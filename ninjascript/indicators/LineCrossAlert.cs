#region Using declarations
using System;
using System.ComponentModel.DataAnnotations;
using NinjaTrader.Cbi;
using NinjaTrader.Gui;
using NinjaTrader.NinjaScript;
using NinjaTrader.Custom.AlertUtils;
#endregion

// Phase 1 acceptance test: prove the whole alert path (chart -> sound -> phone)
// with ZERO strategy risk. Set TriggerPrice to a level (it draws as a line you
// can move), pick a Direction, and when price crosses it you get a chart marker,
// a sound, and a Discord push. See docs/phase1-acceptance.md.
namespace NinjaTrader.NinjaScript.Indicators
{
    public class LineCrossAlert : Indicator
    {
        private bool armed = true;

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Description = "Fires a chart marker + sound + phone push when price crosses a line.";
                Name        = "LineCrossAlert";
                IsOverlay   = true;
                Calculate   = Calculate.OnBarClose;   // matches strategy semantics

                TriggerPrice = 0;
                Direction    = CrossDirection.CrossAbove;
                RearmEachBar = false;
                PlaySound    = true;
                SoundFile    = @"Alert1.wav";
            }
            else if (State == State.Configure)
            {
                AddPlot(System.Windows.Media.Brushes.Goldenrod, "TriggerLine");
            }
        }

        protected override void OnBarUpdate()
        {
            if (TriggerPrice <= 0 || CurrentBar < 1)
                return;

            Values[0][0] = TriggerPrice;   // draw the reference line

            if (RearmEachBar)
                armed = true;

            if (!armed)
                return;

            bool crossed =
                Direction == CrossDirection.CrossAbove
                    ? CrossAbove(Close, TriggerPrice, 1)
                    : CrossBelow(Close, TriggerPrice, 1);

            if (!crossed)
                return;

            armed = false;  // one shot until re-armed

            string arrow = Direction == CrossDirection.CrossAbove ? "▲" : "▼";
            string msg = $"{arrow} {Instrument.MasterInstrument.Name} crossed "
                       + $"{Direction} {TriggerPrice} @ {Close[0]}  ({Time[0]:HH:mm:ss})";

            Draw.TextFixed(this, "cross", msg, TextPosition.TopRight);
            Draw.ArrowUp(this, "arrow" + CurrentBar, false, 0, Low[0] - TickSize * 4,
                Direction == CrossDirection.CrossAbove
                    ? System.Windows.Media.Brushes.LimeGreen
                    : System.Windows.Media.Brushes.Red);

            if (PlaySound && !string.IsNullOrWhiteSpace(SoundFile))
                Alert("linecross", Priority.High, msg, SoundFile, 0,
                      System.Windows.Media.Brushes.Black,
                      System.Windows.Media.Brushes.Goldenrod);

            AlertSender.Send(msg);   // <- phone buzzes
        }

        public enum CrossDirection { CrossAbove, CrossBelow }

        #region Properties
        [NinjaScriptProperty]
        [Display(Name = "Trigger price", Order = 1, GroupName = "Parameters")]
        public double TriggerPrice { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Direction", Order = 2, GroupName = "Parameters")]
        public CrossDirection Direction { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Re-arm each bar", Order = 3, GroupName = "Parameters")]
        public bool RearmEachBar { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Play sound", Order = 4, GroupName = "Alert")]
        public bool PlaySound { get; set; }

        [Display(Name = "Sound file", Order = 5, GroupName = "Alert")]
        public string SoundFile { get; set; }
        #endregion
    }
}
