"""Send a phone push from Python (Telegram or Discord). Mirrors AlertSender.cs.

Use it to smoke-test the alert path in Phase 1, and from any Python tooling
(e.g. a dashboard cron that pings you when you hit your daily target).

    python tools/send_alert.py "message text"

Reads credentials from .env (see .env.example). Never commit .env.
"""
from __future__ import annotations

import os
import sys

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))
except ImportError:
    pass  # dotenv optional; env vars still work

import requests


def send(message: str) -> bool:
    channel = os.getenv("ALERT_CHANNEL", "discord").lower()

    if channel == "telegram":
        token = os.getenv("TELEGRAM_BOT_TOKEN")
        chat = os.getenv("TELEGRAM_CHAT_ID")
        if not token or not chat:
            print("Missing TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID in .env", file=sys.stderr)
            return False
        r = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data={"chat_id": chat, "text": message},
            timeout=10,
        )
        r.raise_for_status()
        return True

    if channel == "discord":
        hook = os.getenv("DISCORD_WEBHOOK_URL")
        if not hook:
            print("Missing DISCORD_WEBHOOK_URL in .env", file=sys.stderr)
            return False
        r = requests.post(hook, json={"content": message}, timeout=10)
        r.raise_for_status()
        return True

    print(f"Unknown ALERT_CHANNEL {channel!r} (use 'telegram' or 'discord')",
          file=sys.stderr)
    return False


if __name__ == "__main__":
    msg = " ".join(sys.argv[1:]) or "Test alert from tools/send_alert.py"
    ok = send(msg)
    print("sent" if ok else "failed")
    sys.exit(0 if ok else 1)
