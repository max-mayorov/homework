"""Switches that choose where reports go: Telegram, the receipt printer, or both.

A switch is unavailable until its channel is set up in the integration's options. Its state is
kept across restarts.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import STATE_OFF, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from . import HomeworkConfigEntry
from .entity import HomeworkEntity


async def async_setup_entry(hass: HomeAssistant, entry: HomeworkConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    async_add_entities([TelegramSwitch(entry, "telegram"), PrintingSwitch(entry, "printing")])


class _ChannelSwitch(HomeworkEntity, SwitchEntity, RestoreEntity):
    _attr_entity_category = EntityCategory.CONFIG
    _attr_is_on = True

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if (last := await self.async_get_last_state()) is not None:
            self._attr_is_on = last.state != STATE_OFF
        self._set(self._attr_is_on)

    async def async_turn_on(self, **kwargs: Any) -> None:
        self._set(True)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        self._set(False)
        self.async_write_ha_state()

    def _set(self, on: bool) -> None:
        raise NotImplementedError


class TelegramSwitch(_ChannelSwitch):
    @property
    def available(self) -> bool:
        return self.reporter.has_telegram

    def _set(self, on: bool) -> None:
        self._attr_is_on = self.reporter.telegram_on = on


class PrintingSwitch(_ChannelSwitch):
    @property
    def available(self) -> bool:
        return self.reporter.has_printer

    def _set(self, on: bool) -> None:
        self._attr_is_on = self.reporter.printing_on = on
