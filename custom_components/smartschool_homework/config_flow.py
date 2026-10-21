"""Set up a Smartschool account (checked by logging in), and the optional Telegram and printer options."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.selector import TextSelector, TextSelectorConfig, TextSelectorType

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
from .core.fetch import TZ, fetch
from .core.printer import parse_address
from .reporter import to_settings

_LOGGER = logging.getLogger(__name__)

_PASSWORD = TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))


def _account_schema(defaults: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_MAIN_URL, default=defaults.get(CONF_MAIN_URL, vol.UNDEFINED)): str,
            vol.Required(CONF_USERNAME, default=defaults.get(CONF_USERNAME, vol.UNDEFINED)): str,
            vol.Required(CONF_PASSWORD): _PASSWORD,
            vol.Required(CONF_MFA): _PASSWORD,
        }
    )


def _clean(user_input: dict[str, Any]) -> dict[str, Any]:
    host = user_input[CONF_MAIN_URL].strip().removeprefix("https://").removeprefix("http://").strip("/")
    return {**user_input, CONF_MAIN_URL: host, CONF_USERNAME: user_input[CONF_USERNAME].strip()}


def _try_login(settings: dict[str, str]) -> str | None:
    """Log in and read the planner, as a report would. Returns an error key for the form, or None. Runs in the executor."""
    from smartschool import SmartSchoolAuthenticationError
    from requests import RequestException

    try:
        fetch(settings, datetime.now(TZ).date())
    except SmartSchoolAuthenticationError:
        return "invalid_auth"
    except RequestException:
        return "cannot_connect"
    except Exception:  # noqa: BLE001 - shown in the form; details in the log
        _LOGGER.exception("Unexpected error while checking the Smartschool login")
        return "unknown"
    return None


async def _check_account(hass: HomeAssistant, data: dict[str, Any]) -> str | None:
    return await hass.async_add_executor_job(_try_login, to_settings(data))


class HomeworkConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            data = _clean(user_input)
            await self.async_set_unique_id(f"{data[CONF_MAIN_URL]}/{data[CONF_USERNAME]}".lower())
            self._abort_if_unique_id_configured()
            if not (error := await _check_account(self.hass, data)):
                return self.async_create_entry(title=f"{data[CONF_USERNAME]} ({data[CONF_MAIN_URL]})", data=data)
            errors["base"] = error
        return self.async_show_form(step_id="user", data_schema=_account_schema(user_input or {}), errors=errors)

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Change the password, MFA answer or school (the same child account)."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            data = _clean(user_input)
            await self.async_set_unique_id(f"{data[CONF_MAIN_URL]}/{data[CONF_USERNAME]}".lower())
            self._abort_if_unique_id_mismatch(reason="wrong_account")
            if not (error := await _check_account(self.hass, data)):
                return self.async_update_reload_and_abort(entry, data=data)
            errors["base"] = error
        return self.async_show_form(step_id="reconfigure", data_schema=_account_schema(user_input or dict(entry.data)), errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry) -> OptionsFlow:
        return HomeworkOptionsFlow()


class HomeworkOptionsFlow(OptionsFlow):
    """Telegram and the receipt printer. Leave a field empty to not use it."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            options = {k: v.strip() for k, v in user_input.items() if isinstance(v, str) and v.strip()}
            if bool(options.get(CONF_TELEGRAM_BOT_TOKEN)) != bool(options.get(CONF_TELEGRAM_CHAT_ID)):
                errors["base"] = "telegram_incomplete"
            if address := options.get(CONF_PRINTER_ADDRESS):
                try:
                    parse_address(address)
                except ValueError:
                    errors[CONF_PRINTER_ADDRESS] = "invalid_printer_address"
            if not errors:
                return self.async_create_entry(data=options)

        current = user_input or self.config_entry.options
        fields = {
            CONF_TELEGRAM_BOT_TOKEN: _PASSWORD,
            CONF_TELEGRAM_CHAT_ID: str,
            CONF_PRINTER_ADDRESS: str,
            CONF_PRINTER_FONT: str,
            CONF_PRINTER_FONT_BOLD: str,
        }
        schema = vol.Schema({vol.Optional(key, description={"suggested_value": current.get(key)}): kind for key, kind in fields.items()})
        return self.async_show_form(step_id="init", data_schema=schema, errors=errors)
