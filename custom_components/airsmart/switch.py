"""Switch platform: the summer bypass."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
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
    """Set up the AirSmart bypass switch."""
    async_add_entities([AirSmartBypassSwitch(entry.runtime_data)])


class AirSmartBypassSwitch(AirSmartEntity, SwitchEntity):
    """Open (on) or close (off) the heat-exchanger bypass."""

    _attr_translation_key = "bypass"
    _attr_device_class = SwitchDeviceClass.SWITCH
    _attr_icon = "mdi:valve"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.device_topic}_bypass"

    @property
    def is_on(self) -> bool | None:
        # NOTE: polarity may be inverted on some units. Observed traffic is
        # ambiguous: after "close_bypass" bypass_status went to 1 and after
        # "open_bypass" to 0, yet on a warm day (bypass presumably open) it also
        # read 1. If your switch ends up inverted, flip the bool here and in
        # binary_sensor.py.
        value = self.coordinator.data.get("bypass_status")
        return None if value is None else bool(value)

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.async_set_bypass(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.async_set_bypass(False)
