"""Smartschool Homework: send the Homework and Results reports from Home Assistant.

Buttons send a report now; the `send_homework_report` and `send_results_report` services do
the same from automations (that's where the schedule lives) and return the report's text.
Switches choose whether reports go to Telegram, the receipt printer, or both.
"""

from __future__ import annotations

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import (
    ATTR_CONFIG_ENTRY_ID,
    ATTR_DATE,
    ATTR_PRINT,
    ATTR_SINCE,
    ATTR_TELEGRAM,
    DOMAIN,
    SERVICE_HOMEWORK_REPORT,
    SERVICE_RESULTS_REPORT,
)
from .reporter import Reporter

PLATFORMS = [Platform.BUTTON, Platform.SWITCH]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

type HomeworkConfigEntry = ConfigEntry[Reporter]

_COMMON = {
    vol.Optional(ATTR_CONFIG_ENTRY_ID): cv.string,
    vol.Optional(ATTR_TELEGRAM): cv.boolean,
    vol.Optional(ATTR_PRINT): cv.boolean,
}
HOMEWORK_SCHEMA = vol.Schema({**_COMMON, vol.Optional(ATTR_DATE): cv.date})
RESULTS_SCHEMA = vol.Schema({**_COMMON, vol.Optional(ATTR_SINCE): cv.date})


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    async def homework_report(call: ServiceCall) -> ServiceResponse:
        reporter = _reporter(hass, call)
        report = await reporter.homework_report(call.data.get(ATTR_DATE), call.data.get(ATTR_TELEGRAM), call.data.get(ATTR_PRINT), preview_ok=call.return_response)
        return report if call.return_response else None

    async def results_report(call: ServiceCall) -> ServiceResponse:
        reporter = _reporter(hass, call)
        report = await reporter.results_report(call.data.get(ATTR_SINCE), call.data.get(ATTR_TELEGRAM), call.data.get(ATTR_PRINT), preview_ok=call.return_response)
        return report if call.return_response else None

    hass.services.async_register(DOMAIN, SERVICE_HOMEWORK_REPORT, homework_report, schema=HOMEWORK_SCHEMA, supports_response=SupportsResponse.OPTIONAL)
    hass.services.async_register(DOMAIN, SERVICE_RESULTS_REPORT, results_report, schema=RESULTS_SCHEMA, supports_response=SupportsResponse.OPTIONAL)
    return True


def _reporter(hass: HomeAssistant, call: ServiceCall) -> Reporter:
    """The Reporter of the entry named in the call, or of the only entry if there's just one."""
    loaded = [e for e in hass.config_entries.async_entries(DOMAIN) if e.state is ConfigEntryState.LOADED]
    if entry_id := call.data.get(ATTR_CONFIG_ENTRY_ID):
        loaded = [e for e in loaded if e.entry_id == entry_id]
        if not loaded:
            raise ServiceValidationError(f"No loaded Smartschool Homework entry with id {entry_id}")
    elif len(loaded) != 1:
        raise ServiceValidationError("Pick the Smartschool account with config_entry_id" if loaded else "Smartschool Homework isn't set up")
    return loaded[0].runtime_data


async def async_setup_entry(hass: HomeAssistant, entry: HomeworkConfigEntry) -> bool:
    entry.runtime_data = Reporter(hass, entry)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_options_updated))
    return True


async def _options_updated(hass: HomeAssistant, entry: HomeworkConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: HomeworkConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
