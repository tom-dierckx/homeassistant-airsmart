"""Button platform: one-shot actions (filter reset, clock sync)."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AirSmartConfigEntry
from .entity import AirSmartEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AirSmartConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the AirSmart buttons."""
    coordinator = entry.runtime_data
    async_add_entities(
        [
            AirSmartResetFilterButton(coordinator),
            AirSmartSyncClockButton(coordinator),
        ]
    )


class AirSmartResetFilterButton(AirSmartEntity, ButtonEntity):
    """Reset the clean-filter timer (serialsend filter_counter = 0)."""

    _attr_translation_key = "reset_filter"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:air-filter"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.device_topic}_reset_filter"

    async def async_press(self) -> None:
        await self.coordinator.async_reset_filter()


class AirSmartSyncClockButton(AirSmartEntity, ButtonEntity):
    """Push Home Assistant's time to the unit's RTC (serialsend time = {...})."""

    _attr_translation_key = "sync_clock"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:clock-check-outline"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.device_topic}_sync_clock"

    async def async_press(self) -> None:
        await self.coordinator.async_sync_clock()
