# Copied from notify.py at the top of the repo by scripts/sync_ha_core.py. Edit that file, not this one.
"""Send text to a Telegram chat via the Bot API."""

from __future__ import annotations

import logging

import requests

log = logging.getLogger(__name__)

MAX_LEN = 4096  # Telegram's limit per message, counted in UTF-16 code units


class TelegramError(RuntimeError):
    pass


def _units(s: str) -> int:
    return len(s.encode("utf-16-le")) // 2


def _hard_split(line: str, limit: int) -> list[str]:
    parts, current = [], ""
    for ch in line:
        if _units(current) + _units(ch) > limit:
            parts.append(current)
            current = ""
        current += ch
    return parts + [current] if current else parts


def split_message(text: str, limit: int = MAX_LEN) -> list[str]:
    """Split text into chunks of at most `limit` units, breaking at line ends where possible."""
    chunks: list[str] = []
    current = ""
    for line in text.splitlines(keepends=True):
        if _units(line) > limit:
            if current:
                chunks.append(current)
                current = ""
            chunks.extend(_hard_split(line, limit))
            continue
        if _units(current) + _units(line) > limit:
            chunks.append(current)
            current = ""
        current += line
    if current:
        chunks.append(current)
    return [c.strip("\n") for c in chunks if c.strip()]


def send(settings: dict[str, str], text: str) -> None:
    token = settings.get("TELEGRAM_BOT_TOKEN")
    chat_id = settings.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        raise RuntimeError("Missing setting: TELEGRAM_BOT_TOKEN and/or TELEGRAM_CHAT_ID")

    chunks = split_message(text)
    for chunk in chunks:
        try:
            r = requests.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": chat_id, "text": chunk, "disable_web_page_preview": True},
                timeout=30,
            )
        except requests.RequestException as exc:
            # The exception text contains the URL, which contains the bot token: don't chain it.
            raise TelegramError(f"Could not reach Telegram ({type(exc).__name__})") from None
        try:
            body = r.json()
        except ValueError:
            body = {}
        if not r.ok or not body.get("ok"):
            raise TelegramError(f"Telegram API error {r.status_code}: {body.get('description', 'no description')}")
    log.info("Sent %d Telegram message(s)", len(chunks))
