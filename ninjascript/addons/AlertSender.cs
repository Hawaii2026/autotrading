#region Using declarations
using System;
using System.Collections.Generic;
using System.IO;
using System.Net.Http;
using System.Text;
using System.Threading.Tasks;
#endregion

// Shared, fire-and-forget phone-push helper used by both the alert indicator and
// the strategy (ALERT mode). Keeps the Telegram/Discord secret OUT of compiled
// code: it reads credentials from environment variables, or from a small json
// config in your NinjaTrader user folder. Nothing here ever blocks the UI thread.
//
// Config resolution order (first hit wins):
//   1. Environment variables: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, DISCORD_WEBHOOK_URL
//   2. File: <MyDocuments>\NinjaTrader 8\alert_config.txt   (key=value per line)
//
// alert_config.txt example (this file is your .env equivalent on Windows):
//   TELEGRAM_BOT_TOKEN=123456:abcdef
//   TELEGRAM_CHAT_ID=987654321
//   DISCORD_WEBHOOK_URL=
namespace NinjaTrader.Custom.AlertUtils
{
    public static class AlertSender
    {
        // One shared HttpClient for the process lifetime (best practice).
        private static readonly HttpClient Http = new HttpClient
        {
            Timeout = TimeSpan.FromSeconds(8)
        };

        private static Dictionary<string, string> _config;

        private static Dictionary<string, string> Config()
        {
            if (_config != null) return _config;
            _config = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);

            void Take(string key)
            {
                var v = Environment.GetEnvironmentVariable(key);
                if (!string.IsNullOrWhiteSpace(v)) _config[key] = v.Trim();
            }
            Take("TELEGRAM_BOT_TOKEN");
            Take("TELEGRAM_CHAT_ID");
            Take("DISCORD_WEBHOOK_URL");

            try
            {
                var path = Path.Combine(
                    Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments),
                    "NinjaTrader 8", "alert_config.txt");
                if (File.Exists(path))
                {
                    foreach (var line in File.ReadAllLines(path))
                    {
                        var idx = line.IndexOf('=');
                        if (idx <= 0) continue;
                        var k = line.Substring(0, idx).Trim();
                        var val = line.Substring(idx + 1).Trim();
                        if (!_config.ContainsKey(k) && !string.IsNullOrWhiteSpace(val))
                            _config[k] = val;
                    }
                }
            }
            catch { /* config file is optional */ }

            return _config;
        }

        /// <summary>
        /// Push a message to your phone. Non-blocking; failures are swallowed so a
        /// dead network can never stall the chart or the order path.
        /// </summary>
        public static void Send(string message)
        {
            var cfg = Config();
            try
            {
                if (cfg.TryGetValue("TELEGRAM_BOT_TOKEN", out var token)
                    && cfg.TryGetValue("TELEGRAM_CHAT_ID", out var chat)
                    && !string.IsNullOrWhiteSpace(token))
                {
                    var url = $"https://api.telegram.org/bot{token}/sendMessage";
                    var content = new FormUrlEncodedContent(new[]
                    {
                        new KeyValuePair<string, string>("chat_id", chat),
                        new KeyValuePair<string, string>("text", message),
                    });
                    _ = FireAndForget(url, content);
                    return;
                }

                if (cfg.TryGetValue("DISCORD_WEBHOOK_URL", out var hook)
                    && !string.IsNullOrWhiteSpace(hook))
                {
                    var json = "{\"content\":" + JsonString(message) + "}";
                    var content = new StringContent(json, Encoding.UTF8, "application/json");
                    _ = FireAndForget(hook, content);
                }
            }
            catch { /* never let alerting throw into strategy code */ }
        }

        private static async Task FireAndForget(string url, HttpContent content)
        {
            try { await Http.PostAsync(url, content).ConfigureAwait(false); }
            catch { /* swallow: alerts are best-effort */ }
        }

        // Minimal JSON string escaper (avoids a serializer dependency).
        private static string JsonString(string s)
        {
            var sb = new StringBuilder("\"");
            foreach (var c in s)
            {
                switch (c)
                {
                    case '"': sb.Append("\\\""); break;
                    case '\\': sb.Append("\\\\"); break;
                    case '\n': sb.Append("\\n"); break;
                    case '\r': sb.Append("\\r"); break;
                    case '\t': sb.Append("\\t"); break;
                    default: sb.Append(c); break;
                }
            }
            return sb.Append('"').ToString();
        }
    }
}
