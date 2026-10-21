"""Build the Homework and Results reports and deliver them to Telegram and/or the receipt printer.

The same steps as main.py, but called from buttons and service calls instead of cron. The
smartschool library, Telegram and the printer all block, so they run in the executor.
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
    CONF_TELEGRAM_BOT_TOKEN,
    CONF_TELEGRAM_CHAT_ID,
    DOMAIN,
)
from .core.errors import error_message, redact
from .core.fetch import TZ, fetch
from .core.message import build_message, build_results_message
from .core.notify import send
from .core.printer import print_image, render_report, render_results
from .core.results import fetch_results, window_start

_LOGGER = logging.getLogger(__name__)

TELEGRAM, PRINTING = "sending to Telegram", "printing"

# Config entry keys -> the setting names the app's modules use
SETTING_NAMES = {
    CONF_USERNAME: "SMARTSCHOOL_USERNAME",
    CONF_PASSWORD: "SMARTSCHOOL_PASSWORD",
    CONF_MAIN_URL: "SMARTSCHOOL_MAIN_URL",
    CONF_MFA: "SMARTSCHOOL_MFA",
    CONF_TELEGRAM_BOT_TOKEN: "TELEGRAM_BOT_TOKEN",
    CONF_TELEGRAM_CHAT_ID: "TELEGRAM_CHAT_ID",
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


def has_telegram(settings: Mapping[str, str]) -> bool:
    return bool(settings.get("TELEGRAM_BOT_TOKEN") and settings.get("TELEGRAM_CHAT_ID"))


def has_printer(settings: Mapping[str, str]) -> bool:
    return bool(settings.get("PRINTER_ADDRESS"))


class Reporter:
    """One per config entry. The Telegram and printing switches set `telegram_on` and `printing_on`."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.settings = to_settings(entry.data, entry.options)
        self.telegram_on = True
        self.printing_on = True
        self._lock = asyncio.Lock()  # one report at a time, e.g. when a button is pressed twice
        self._store: Store[dict[str, str]] = Store(hass, 1, f"{DOMAIN}.{entry.entry_id}")

    def channels(self, telegram: bool | None, printing: bool | None, preview_ok: bool) -> tuple[bool, bool]:
        """Where to deliver: the switches, unless the call says otherwise. Raises if there's nowhere to deliver and `preview_ok` is False."""
        if telegram and not has_telegram(self.settings):
            raise ServiceValidationError("Telegram isn't set up: add the bot token and chat id in the integration's options")
        if printing and not has_printer(self.settings):
            raise ServiceValidationError("The receipt printer isn't set up: add its address in the integration's options")
        telegram = (self.telegram_on if telegram is None else telegram) and has_telegram(self.settings)
        printing = (self.printing_on if printing is None else printing) and has_printer(self.settings)
        if not (telegram or printing or preview_ok):
            raise ServiceValidationError("Nowhere to send the report: Telegram and printing are both off or not set up")
        return telegram, printing

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
            except Exception as exc:  # noqa: BLE001 - every failure must reach the parent
                await self._fail(step, exc, "Homework", telegram)
            failed = await self._deliver(text, lambda: render_report(items, today, settings), "Homework", telegram, printing)
        self._raise_if_failed(failed, "Homework")
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
            except Exception as exc:  # noqa: BLE001 - every failure must reach the parent
                await self._fail(step, exc, "Results", telegram)
            failed = await self._deliver(text, lambda: render_results(results, settings, now), "Results", telegram, printing) if results else []
            # Delivered once Telegram has it (or the printer, without Telegram); a preview doesn't count
            first = TELEGRAM if telegram else PRINTING if printing else None
            if first and first not in failed:
                await self._store.async_save({"last_results_run": now.isoformat()})
        self._raise_if_failed(failed, "Results")
        return {"message": text, "count": len(results), "since": start.isoformat()}

    async def _load_last_run(self) -> datetime | None:
        data = await self._store.async_load() or {}
        try:
            return datetime.fromisoformat(data["last_results_run"])
        except (KeyError, ValueError):
            return None

    async def _deliver(self, text: str, render: Callable[[], Any], check: str, telegram: bool, printing: bool) -> dict[str, BaseException]:
        """Send to Telegram and print, independently: one failing doesn't stop the other. Returns the failed steps."""
        failed: dict[str, BaseException] = {}
        if telegram:
            try:
                await self.hass.async_add_executor_job(send, self.settings, text)
            except Exception as exc:  # noqa: BLE001
                failed[TELEGRAM] = exc
        if printing:
            try:
                img = await self.hass.async_add_executor_job(render)
                await self.hass.async_add_executor_job(print_image, self.settings["PRINTER_ADDRESS"], img)
            except Exception as exc:  # noqa: BLE001
                failed[PRINTING] = exc
                if telegram and TELEGRAM not in failed:
                    await self._send_error(error_message(PRINTING, exc, self.settings, check))
        return failed

    def _raise_if_failed(self, failed: dict[str, BaseException], check: str) -> None:
        if failed:
            messages = [error_message(step, exc, self.settings, check) for step, exc in failed.items()]
            for message in messages:
                _LOGGER.error("%s", message)
            raise HomeAssistantError("\n".join(messages))

    async def _fail(self, step: str, exc: BaseException, check: str, telegram: bool):
        """Report a failure before anything was delivered: to Telegram if it's on, and as the call's error."""
        message = error_message(step, exc, self.settings, check)
        _LOGGER.error("%s", message)
        if telegram:
            await self._send_error(message)
        raise HomeAssistantError(message) from None

    async def _send_error(self, message: str) -> None:
        try:
            await self.hass.async_add_executor_job(send, self.settings, message)
        except Exception as exc:  # noqa: BLE001
            _LOGGER.error("Could not send the error to Telegram either: %s", redact(str(exc), self.settings))
