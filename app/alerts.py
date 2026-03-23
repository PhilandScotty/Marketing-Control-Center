"""Multi-level alert system for MCC.

Level 1: Internal dashboard (staleness detection) — always active
Level 2: Telegram bot alerts — requires TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID
Level 3: External dead man's switch (Healthchecks.io) — runs independently via cron
"""
import logging
import urllib.request
import urllib.parse
import json

from app.config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, HEALTHCHECKS_PING_URL

logger = logging.getLogger("mcc.alerts")


def send_telegram(message: str, parse_mode: str = "HTML") -> bool:
    """Send a Telegram message. Returns True on success."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.debug("Telegram not configured — skipping alert")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = json.dumps({
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": parse_mode,
    }).encode()

    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status == 200:
                logger.info("Telegram alert sent")
                return True
            else:
                logger.warning(f"Telegram returned status {resp.status}")
                return False
    except Exception as e:
        logger.error(f"Telegram alert failed: {e}")
        return False


def send_critical_alert(title: str, body: str = "") -> bool:
    """Send a critical alert via Telegram (Level 2)."""
    msg = f"🚨 <b>MCC CRITICAL</b>\n\n<b>{title}</b>"
    if body:
        msg += f"\n{body}"
    return send_telegram(msg)


def send_warning_alert(title: str, body: str = "") -> bool:
    """Send a warning alert via Telegram."""
    msg = f"⚠️ <b>MCC Warning</b>\n\n<b>{title}</b>"
    if body:
        msg += f"\n{body}"
    return send_telegram(msg)


def ping_healthchecks(status: str = "ok") -> bool:
    """Ping Healthchecks.io dead man's switch (Level 3).
    status: 'ok', 'start', 'fail'
    """
    if not HEALTHCHECKS_PING_URL:
        return False

    url = HEALTHCHECKS_PING_URL
    if status == "fail":
        url += "/fail"
    elif status == "start":
        url += "/start"

    try:
        req = urllib.request.Request(url, method="POST", data=b"")
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status == 200
    except Exception as e:
        logger.error(f"Healthchecks.io ping failed: {e}")
        return False


def test_telegram() -> dict:
    """Test Telegram connectivity. Returns status dict."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return {"configured": False, "working": False, "error": "TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set"}

    ok = send_telegram("✅ MCC Telegram alert test — this message confirms alerts are working.")
    return {"configured": True, "working": ok, "error": None if ok else "Failed to send test message"}


def test_healthchecks() -> dict:
    """Test Healthchecks.io connectivity."""
    if not HEALTHCHECKS_PING_URL:
        return {"configured": False, "working": False, "error": "HEALTHCHECKS_PING_URL not set"}

    ok = ping_healthchecks("ok")
    return {"configured": True, "working": ok, "error": None if ok else "Failed to ping"}
