"""Select platform: the ventilation level (Low / Medium / High / Boost)."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AirSmartConfigEntry
from .const import DATA_SETPOINT, VENTILATION_LEVELS
from .entity import AirSmartEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AirSmartConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the AirSmart ventilation-level select."""
    async_add_entities([AirSmartVentilationLevel(entry.runtime_data)])


class AirSmartVentilationLevel(AirSmartEntity, SelectEntity):
    """The unit's ventilation level; setpoint 0-3 -> Low/Medium/High/Boost."""

    _attr_translation_key = "ventilation_level"
    _attr_options = list(VENTILATION_LEVELS)
    _attr_icon = "mdi:fan"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.device_topic}_ventilation_level"

    @property
    def current_option(self) -> str | None:
        level = self.coordinator.data.get(DATA_SETPOINT)
        if level is None or not 0 <= level < len(VENTILATION_LEVELS):
            return None
        return VENTILATION_LEVELS[level]

    async def async_select_option(self, option: str) -> None:
        await self.coordinator.async_set_level(VENTILATION_LEVELS.index(option))
