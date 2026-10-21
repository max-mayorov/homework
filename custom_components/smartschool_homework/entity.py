"""Base entity: every entity belongs to one device per Smartschool account."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import CONF_MAIN_URL, DOMAIN
from .reporter import Reporter


class HomeworkEntity(Entity):
    _attr_has_entity_name = True

    def __init__(self, entry: ConfigEntry, key: str) -> None:
        self.reporter: Reporter = entry.runtime_data
        self._attr_translation_key = key
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="Smartschool",
            entry_type=DeviceEntryType.SERVICE,
            configuration_url=f"https://{entry.data[CONF_MAIN_URL]}",
        )
