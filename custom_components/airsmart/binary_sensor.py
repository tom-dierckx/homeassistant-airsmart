"""Binary sensor platform: alarms, warnings and frost/bypass state."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AirSmartConfigEntry
from .entity import AirSmartEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class AirSmartBinaryDescription(BinarySensorEntityDescription):
    """Describes an AirSmart binary sensor."""

    value_fn: Callable[[dict[str, Any]], bool | None] = lambda data: None


def _flag(key: str) -> Callable[[dict[str, Any]], bool | None]:
    def _get(data: dict[str, Any]) -> bool | None:
        value = data.get(key)
        return None if value is None else bool(value)

    return _get


BINARY_SENSORS: tuple[AirSmartBinaryDescription, ...] = (
    AirSmartBinaryDescription(
        key="alarm1",
        translation_key="alarm1",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=_flag("alarm1"),
    ),
    AirSmartBinaryDescription(
        key="alarm2",
        translation_key="alarm2",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=_flag("alarm2"),
    ),
    AirSmartBinaryDescription(
        key="warning",
        translation_key="warning",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=_flag("warning"),
    ),
    AirSmartBinaryDescription(
        key="frostprotect_status",
        translation_key="frostprotect_status",
        device_class=BinarySensorDeviceClass.COLD,
        value_fn=_flag("frostprotect_status"),
    ),
    AirSmartBinaryDescription(
        key="frost_protect_inlet_off",
        translation_key="frost_protect_inlet_off",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_flag("frost_protect_inlet_off"),
    ),
    AirSmartBinaryDescription(
        key="frot_protect_unbal",
        translation_key="frost_protect_unbalanced",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_flag("frot_protect_unbal"),
    ),
    AirSmartBinaryDescription(
        key="bypass_status",
        translation_key="bypass_status",
        device_class=BinarySensorDeviceClass.OPENING,
        value_fn=_flag("bypass_status"),
    ),
    AirSmartBinaryDescription(
        key="bypass_in_manual",
        translation_key="bypass_in_manual",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_flag("bypass_in_manual"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AirSmartConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the AirSmart binary sensors."""
    coordinator = entry.runtime_data
    async_add_entities(
        AirSmartBinarySensor(coordinator, desc) for desc in BINARY_SENSORS
    )


class AirSmartBinarySensor(AirSmartEntity, BinarySensorEntity):
    """A single alarm/warning/state flag."""

    entity_description: AirSmartBinaryDescription

    def __init__(self, coordinator, description: AirSmartBinaryDescription) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.device_topic}_{description.key}"

    @property
    def is_on(self) -> bool | None:
        return self.entity_description.value_fn(self.coordinator.data)
