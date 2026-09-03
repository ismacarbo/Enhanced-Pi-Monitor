"""Best-effort Telegram notifications."""

import logging

import requests

from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID


LOGGER = logging.getLogger(__name__)


def send_telegram_alert(message: str):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        LOGGER.debug("Telegram notification skipped: integration not configured")
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        resp = requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": message}, timeout=5)
        if resp.status_code != 200:
            LOGGER.warning("Telegram notification failed with HTTP %s", resp.status_code)
            return False
    except requests.RequestException as exc:
        LOGGER.warning("Telegram notification failed: %s", exc)
        return False
    return True
