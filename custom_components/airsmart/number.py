"""Number platform: the unit's "extra settings".

Each of these is sent as {"payload":{<key>:<int>},"id":"<rand32>"} on the
serialsend topic and echoed back on tele/RESULT.
"""

from __future__ import annotations

from homeassistant.components.number import (
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AirSmartConfigEntry
from .const import KEY_BOOST_TIMER, LEVEL_SETPOINT_KEYS
from .entity import AirSmartEntity

PARALLEL_UPDATES = 0

NUMBERS: tuple[NumberEntityDescription, ...] = (
    NumberEntityDescription(
        key=KEY_BOOST_TIMER,
        translation_key="boost_timer",
        native_min_value=0,
        native_max_value=180,
        native_step=1,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        mode=NumberMode.BOX,
        entity_category=EntityCategory.CONFIG,
        icon="mdi:timer-cog-outline",
    ),
    *(
        NumberEntityDescription(
            key=key,
            translation_key=key,
            native_min_value=0,
            native_max_value=100,
            native_step=1,
            native_unit_of_measurement=PERCENTAGE,
            mode=NumberMode.SLIDER,
            entity_category=EntityCategory.CONFIG,
            icon="mdi:fan",
        )
        for key in LEVEL_SETPOINT_KEYS
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AirSmartConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the AirSmart configuration numbers."""
    coordinator = entry.runtime_data
    async_add_entities(AirSmartNumber(coordinator, desc) for desc in NUMBERS)


class AirSmartNumber(AirSmartEntity, NumberEntity):
    """A single integer setting on the unit."""

    def __init__(self, coordinator, description: NumberEntityDescription) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.device_topic}_{description.key}"

    @property
    def native_value(self) -> float | None:
        value = self.coordinator.data.get(self.entity_description.key)
        return None if value is None else float(value)

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.async_set_setting(
            self.entity_description.key, int(value)
        )
