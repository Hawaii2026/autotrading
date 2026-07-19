#region Using declarations
using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Threading;
using NinjaTrader.Cbi;
using NinjaTrader.Data;
using NinjaTrader.NinjaScript;
#endregion

// TickRecorder — captures EVERY trade tick locally, on the trading PC.
//
// Why this exists: KarenBridge's cloud feed is latest-value sampled (~2/sec)
// and display-grade. This addon subscribes directly to NT8 market data and
// writes every Last tick to daily CSV files, giving the Python lab
// research-grade tick data with the SAME clock as NT8 chart exports (so bars
// derived from it align with exported bars without timezone shifts).
//
// READ-ONLY: subscribes to market data and writes local files. It never
// places, modifies, or cancels orders, and nothing leaves the PC.
//
// Config (optional): Documents\NinjaTrader 8\tick_recorder.txt
//   INSTRUMENTS=MNQ 09-26,NQ 09-26,ES 09-26
//   OUTPUT_DIR=C:\path\to\repo\research\data\ticks_nt8     (default below)
// Update INSTRUMENTS on contract rollover. Missing file => defaults apply.
//
// Output: <OUTPUT_DIR>\<INSTRUMENT>\<yyyy-MM-dd>.csv with header
//   time;price;volume        time = "yyyy-MM-dd HH:mm:ss.fff" (NT8 local)
//
// Import into the lab: python -m research.lib.tick_import --help
namespace NinjaTrader.NinjaScript.AddOns
{
    public class TickRecorder : AddOnBase
    {
        private static readonly string[] DefaultInstruments = { "MNQ 09-26" };

        private readonly List<MarketData> subscriptions = new List<MarketData>();
        private readonly ConcurrentQueue<Row> queue = new ConcurrentQueue<Row>();
        private readonly Dictionary<string, StreamWriter> writers =
            new Dictionary<string, StreamWriter>();
        private readonly object writerLock = new object();

        private string[] instruments = DefaultInstruments;
        private string outputDir;
        private Timer flushTimer;
        private int subscribed;
        private long written;

        private struct Row
        {
            public string Instrument;
            public DateTime Time;
            public double Price;
            public long Volume;
        }

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Name = "TickRecorder";
                Description = "Writes every Last tick to local daily CSVs "
                            + "(research-grade capture; read-only, local-only).";
            }
            else if (State == State.Active)
            {
                LoadConfig();
                // Drain the queue to disk every 2s; tick bursts just queue up.
                flushTimer = new Timer(delegate { Flush(); }, null, 2000, 2000);
                TrySubscribe();
            }
            else if (State == State.Terminated)
            {
                Unsubscribe();
                if (flushTimer != null) { flushTimer.Dispose(); flushTimer = null; }
                Flush();
                lock (writerLock)
                {
                    foreach (var w in writers.Values)
                        try { w.Flush(); w.Dispose(); } catch { }
                    writers.Clear();
                }
            }
        }

        protected override void OnConnectionStatusUpdate(ConnectionStatusEventArgs e)
        {
            if (e.Status == ConnectionStatus.Connected)
                TrySubscribe();
        }

        private void LoadConfig()
        {
            string docs = Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments);
            outputDir = Path.Combine(docs, "NinjaTrader 8", "tickdata");
            try
            {
                string path = Path.Combine(docs, "NinjaTrader 8", "tick_recorder.txt");
                if (File.Exists(path))
                {
                    foreach (string raw in File.ReadAllLines(path))
                    {
                        string line = raw.Trim();
                        int idx = line.IndexOf('=');
                        if (line.StartsWith("#") || idx <= 0) continue;
                        string key = line.Substring(0, idx).Trim().ToUpperInvariant();
                        string val = line.Substring(idx + 1).Trim();
                        if (key == "INSTRUMENTS" && val.Length > 0)
                        {
                            var names = new List<string>();
                            foreach (string n in val.Split(','))
                                if (n.Trim().Length > 0) names.Add(n.Trim());
                            if (names.Count > 0) instruments = names.ToArray();
                        }
                        else if (key == "OUTPUT_DIR" && val.Length > 0)
                            outputDir = val;
                    }
                }
            }
            catch (Exception error) { Report("config error: " + error.Message); }
        }

        private void TrySubscribe()
        {
            if (Interlocked.CompareExchange(ref subscribed, 1, 0) != 0)
                return;
            int attached = 0;
            foreach (string name in instruments)
            {
                try
                {
                    Instrument instrument = Instrument.GetInstrument(name);
                    if (instrument == null)
                    {
                        Report("instrument not found yet: " + name);
                        continue;
                    }
                    MarketData marketData = new MarketData(instrument);
                    marketData.Update += OnMarketData;
                    subscriptions.Add(marketData);
                    attached++;
                }
                catch (Exception error)
                {
                    Report("subscribe failed for " + name + ": " + error.Message);
                }
            }
            if (attached == 0)
            {
                // nothing attached (no data connection yet) — retry on next connect
                Interlocked.Exchange(ref subscribed, 0);
                return;
            }
            Report("recording " + string.Join(", ", instruments) + " -> " + outputDir);
        }

        private void Unsubscribe()
        {
            foreach (MarketData marketData in subscriptions)
            {
                try { marketData.Update -= OnMarketData; } catch { }
            }
            subscriptions.Clear();
            Interlocked.Exchange(ref subscribed, 0);
        }

        private void OnMarketData(object sender, MarketDataEventArgs e)
        {
            // EVERY Last tick — no sampling. Bid/Ask updates are skipped to keep
            // files research-focused (trades) and an order of magnitude smaller.
            if (e.MarketDataType != MarketDataType.Last)
                return;
            queue.Enqueue(new Row
            {
                Instrument = e.Instrument.FullName,
                Time = e.Time,
                Price = e.Price,
                Volume = (long)e.Volume,
            });
        }

        private void Flush()
        {
            try
            {
                Row row;
                while (queue.TryDequeue(out row))
                {
                    StreamWriter writer = WriterFor(row.Instrument, row.Time);
                    if (writer == null) continue;
                    writer.Write(row.Time.ToString("yyyy-MM-dd HH:mm:ss.fff",
                        CultureInfo.InvariantCulture));
                    writer.Write(';');
                    writer.Write(row.Price.ToString(CultureInfo.InvariantCulture));
                    writer.Write(';');
                    writer.WriteLine(row.Volume.ToString(CultureInfo.InvariantCulture));
                    written++;
                }
                lock (writerLock)
                {
                    foreach (var w in writers.Values)
                        try { w.Flush(); } catch { }
                }
            }
            catch (Exception error) { Report("flush error: " + error.Message); }
        }

        private StreamWriter WriterFor(string instrument, DateTime time)
        {
            string safe = instrument.Replace(' ', '_').Replace('/', '-');
            string day = time.ToString("yyyy-MM-dd", CultureInfo.InvariantCulture);
            string key = safe + "|" + day;
            lock (writerLock)
            {
                StreamWriter writer;
                if (writers.TryGetValue(key, out writer))
                    return writer;
                try
                {
                    // day rolled: close this instrument's previous writer(s)
                    var staleKeys = new List<string>();
                    foreach (var k in writers.Keys)
                        if (k.StartsWith(safe + "|")) staleKeys.Add(k);
                    foreach (var k in staleKeys)
                    {
                        try { writers[k].Flush(); writers[k].Dispose(); } catch { }
                        writers.Remove(k);
                    }

                    string dir = Path.Combine(outputDir, safe);
                    Directory.CreateDirectory(dir);
                    string path = Path.Combine(dir, day + ".csv");
                    bool isNew = !File.Exists(path);
                    writer = new StreamWriter(path, true);
                    if (isNew)
                        writer.WriteLine("time;price;volume");
                    writers[key] = writer;
                    return writer;
                }
                catch (Exception error)
                {
                    Report("writer error for " + instrument + ": " + error.Message);
                    return null;
                }
            }
        }

        private void Report(string message)
        {
            NinjaTrader.Code.Output.Process("TickRecorder: " + message,
                PrintTo.OutputTab1);
        }
    }
}
