"""Buttons that send a report now, to wherever the Telegram and printing switches say."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HomeworkConfigEntry
from .entity import HomeworkEntity


async def async_setup_entry(hass: HomeAssistant, entry: HomeworkConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    async_add_entities([HomeworkReportButton(entry, "homework_report"), ResultsReportButton(entry, "results_report")])


class HomeworkReportButton(HomeworkEntity, ButtonEntity):
    async def async_press(self) -> None:
        await self.reporter.homework_report()


class ResultsReportButton(HomeworkEntity, ButtonEntity):
    async def async_press(self) -> None:
        await self.reporter.results_report()
