"""Build the Homework and Results reports and deliver them to Telegram and/or the receipt printer.

Uses the reports' logic (the homework package), called from buttons and actions. Telegram
messages go through Home Assistant's Telegram bot integration. Failures are raised as Home
Assistant errors, which HA shows or logs; they aren't sent to Telegram. The smartschool library
and the printer block, so they run in the executor.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable, Mapping
from datetime import date, datetime, time
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.storage import Store

from .const import (
    CONF_MAIN_URL,
    CONF_MFA,
    CONF_PRINTER_ADDRESS,
    CONF_PRINTER_FONT,
    CONF_PRINTER_FONT_BOLD,
    CONF_TELEGRAM_CHAT,
    DOMAIN,
    TELEGRAM_BOT_DOMAIN,
    TELEGRAM_CHAT_SUBENTRY,
)
from .homework.fetch import TZ, fetch
from .homework.message import build_message, build_results_message
from .homework.notify import split_message
from .homework.printer import print_image, render_report, render_results
from .homework.results import fetch_results, window_start

_LOGGER = logging.getLogger(__name__)

TELEGRAM, PRINTING = "sending to Telegram", "printing"

# Masked in error messages
SECRETS = ("SMARTSCHOOL_PASSWORD", "SMARTSCHOOL_MFA", "SMARTSCHOOL_USERNAME")

# Config entry keys -> the setting names the app's modules use
SETTING_NAMES = {
    CONF_USERNAME: "SMARTSCHOOL_USERNAME",
    CONF_PASSWORD: "SMARTSCHOOL_PASSWORD",
    CONF_MAIN_URL: "SMARTSCHOOL_MAIN_URL",
    CONF_MFA: "SMARTSCHOOL_MFA",
    CONF_PRINTER_ADDRESS: "PRINTER_ADDRESS",
    CONF_PRINTER_FONT: "PRINTER_FONT",
    CONF_PRINTER_FONT_BOLD: "PRINTER_FONT_BOLD",
}


def to_settings(*sources: Mapping[str, Any]) -> dict[str, str]:
    """Config entry data/options as the flat settings dict that config.py's load_settings returns."""
    settings: dict[str, str] = {}
    for source in sources:
        for key, name in SETTING_NAMES.items():
            if value := str(source.get(key) or "").strip():
                settings[name] = value
    return settings


def telegram_chat(value: str | None) -> tuple[str, int] | None:
    """The CONF_TELEGRAM_CHAT option, "<telegram_bot config entry id>:<chat id>", as (entry id, chat id)."""
    bot, _, chat_id = (value or "").rpartition(":")
    try:
        return (bot, int(chat_id)) if bot else None
    except ValueError:
        return None


class Reporter:
    """One per config entry. The Telegram and printing switches set `telegram_on` and `printing_on`."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.settings = to_settings(entry.data, entry.options)
        self.telegram_chat = telegram_chat(entry.options.get(CONF_TELEGRAM_CHAT))
        self.telegram_on = True
        self.printing_on = True
        self._lock = asyncio.Lock()  # one report at a time, e.g. when a button is pressed twice
        self._store: Store[dict[str, str]] = Store(hass, 1, f"{DOMAIN}.{entry.entry_id}")

    @property
    def has_telegram(self) -> bool:
        return self.telegram_chat is not None

    @property
    def has_printer(self) -> bool:
        return bool(self.settings.get("PRINTER_ADDRESS"))

    def channels(self, telegram: bool | None, printing: bool | None, preview_ok: bool) -> tuple[bool, bool]:
        """Where to deliver: the switches, unless the call says otherwise. Raises if there's nowhere to deliver and `preview_ok` is False."""
        if telegram and not self.has_telegram:
            raise ServiceValidationError(translation_domain=DOMAIN, translation_key="telegram_not_set_up")
        if printing and not self.has_printer:
            raise ServiceValidationError(translation_domain=DOMAIN, translation_key="printer_not_set_up")
        telegram = (self.telegram_on if telegram is None else telegram) and self.has_telegram
        printing = (self.printing_on if printing is None else printing) and self.has_printer
        if not (telegram or printing or preview_ok):
            raise ServiceValidationError(translation_domain=DOMAIN, translation_key="nowhere_to_send")
        if telegram and not self._telegram_chat_exists():
            raise ServiceValidationError(translation_domain=DOMAIN, translation_key="telegram_chat_gone")
        return telegram, printing

    def _telegram_chat_exists(self) -> bool:
        """Whether the chosen chat is still set up in the Telegram bot integration (it may have been removed since)."""
        bot, chat_id = self.telegram_chat
        entry = self.hass.config_entries.async_get_entry(bot)
        return (
            entry is not None
            and entry.domain == TELEGRAM_BOT_DOMAIN
            and any(chat.subentry_type == TELEGRAM_CHAT_SUBENTRY and chat.data.get("chat_id") == chat_id for chat in entry.subentries.values())
        )

    async def homework_report(self, today: date | None = None, telegram: bool | None = None, printing: bool | None = None, preview_ok: bool = False) -> dict[str, Any]:
        """The Homework report for the next school day after `today`. Returns its text and number of Items."""
        telegram, printing = self.channels(telegram, printing, preview_ok)
        settings = self.settings
        today = today or datetime.now(TZ).date()
        async with self._lock:
            step = "fetching from Smartschool"
            try:
                items = await self.hass.async_add_executor_job(fetch, settings, today)
                step = "building the message"
                text = build_message(items, today)
            except Exception as exc:
                raise self._error("Homework", {step: exc}) from exc
            failed = await self._deliver(text, lambda: render_report(items, today, settings), telegram, printing)
        if failed:
            raise self._error("Homework", failed)
        _LOGGER.debug("Homework report: %d item(s), Telegram %s, printing %s", len(items), telegram, printing)
        return {"message": text, "count": len(items)}

    async def results_report(self, since: date | None = None, telegram: bool | None = None, printing: bool | None = None, preview_ok: bool = False) -> dict[str, Any]:
        """The Results report: Results published since the last delivered one (or since `since`). Nothing is sent if there are none."""
        telegram, printing = self.channels(telegram, printing, preview_ok)
        settings = self.settings
        now = datetime.now(TZ)
        async with self._lock:
            start = datetime.combine(since, time.min, TZ) if since else window_start(await self._load_last_run(), now)
            step = "fetching results from Smartschool"
            try:
                results = await self.hass.async_add_executor_job(fetch_results, settings, start, now)
                step = "building the message"
                text = build_results_message(results) if results else ""
            except Exception as exc:
                raise self._error("Results", {step: exc}) from exc
            failed = await self._deliver(text, lambda: render_results(results, settings, now), telegram, printing) if results else {}
            # Delivered once Telegram has it (or the printer, without Telegram); a preview doesn't count
            first = TELEGRAM if telegram else PRINTING if printing else None
            if first and first not in failed:
                await self._store.async_save({"last_results_run": now.isoformat()})
        if failed:
            raise self._error("Results", failed)
        _LOGGER.debug("Results report: %d new result(s) since %s, Telegram %s, printing %s", len(results), start, telegram, printing)
        return {"message": text, "count": len(results), "since": start.isoformat()}

    async def _load_last_run(self) -> datetime | None:
        data = await self._store.async_load() or {}
        try:
            return datetime.fromisoformat(data["last_results_run"])
        except (KeyError, ValueError):
            return None

    async def _deliver(self, text: str, render: Callable[[], Any], telegram: bool, printing: bool) -> dict[str, Exception]:
        """Send to Telegram and print, independently: one failing doesn't stop the other. Returns the failed steps."""
        failed: dict[str, Exception] = {}
        if telegram:
            try:
                await self._send_telegram(text)
            except Exception as exc:  # noqa: BLE001 - reported with the printer's outcome
                failed[TELEGRAM] = exc
        if printing:
            try:
                img = await self.hass.async_add_executor_job(render)
                await self.hass.async_add_executor_job(print_image, self.settings["PRINTER_ADDRESS"], img)
            except Exception as exc:  # noqa: BLE001 - reported with Telegram's outcome
                failed[PRINTING] = exc
        return failed

    async def _send_telegram(self, text: str) -> None:
        """Send through the Telegram bot integration, as plain text (teachers' text isn't Markdown), split at Telegram's limit."""
        bot, chat_id = self.telegram_chat
        for part in split_message(text):
            # With a response, telegram_bot raises if the chat didn't get the message
            await self.hass.services.async_call(
                TELEGRAM_BOT_DOMAIN,
                "send_message",
                {"config_entry_id": bot, "target": [chat_id], "message": part, "parse_mode": "plain_text", "disable_web_page_preview": True},
                blocking=True,
                return_response=True,
            )

    def _error(self, report: str, failed: dict[str, Exception]) -> HomeAssistantError:
        """One error for the failed steps, with the configured secrets masked. Home Assistant logs or shows it."""
        return HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="report_failed",
            translation_placeholders={
                "report": report,
                "step": " and ".join(failed),
                "error": self._redact("; ".join(f"{type(exc).__name__}: {exc}" for exc in failed.values())),
            },
        )

    def _redact(self, text: str) -> str:
        for name in SECRETS:
            if (value := self.settings.get(name)) and len(value) >= 3:
                text = text.replace(value, "***")
        return text
