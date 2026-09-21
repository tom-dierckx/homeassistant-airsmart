"""Sensor platform: ventilation telemetry plus Tasmota STATE diagnostics."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfInformation,
    UnitOfTemperature,
    UnitOfVolumeFlowRate,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AirSmartConfigEntry
from .const import (
    DATA_HEAP,
    DATA_MQTT_COUNT,
    DATA_UPTIME,
    DATA_WIFI_RSSI,
    DATA_WIFI_SIGNAL,
)
from .entity import AirSmartEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class AirSmartSensorDescription(SensorEntityDescription):
    """Describes an AirSmart sensor."""

    value_fn: Callable[[dict[str, Any]], Any] = lambda data: None


SENSORS: tuple[AirSmartSensorDescription, ...] = (
    AirSmartSensorDescription(
        key="freshair_temp",
        translation_key="freshair_temp",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.get("freshair_temp"),
    ),
    AirSmartSensorDescription(
        key="extraction_temp",
        translation_key="extraction_temp",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.get("extraction_temp"),
    ),
    AirSmartSensorDescription(
        key="q_supply",
        translation_key="q_supply",
        native_unit_of_measurement=UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:fan-chevron-up",
        value_fn=lambda data: data.get("q_supply"),
    ),
    AirSmartSensorDescription(
        key="q_blowoff",
        translation_key="q_blowoff",
        native_unit_of_measurement=UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:fan-chevron-down",
        value_fn=lambda data: data.get("q_blowoff"),
    ),
    AirSmartSensorDescription(
        key="pwm_supply",
        translation_key="pwm_supply",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:fan",
        value_fn=lambda data: data.get("pwm_supply"),
    ),
    AirSmartSensorDescription(
        key="pwm_blowoff",
        translation_key="pwm_blowoff",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:fan",
        value_fn=lambda data: data.get("pwm_blowoff"),
    ),
    AirSmartSensorDescription(
        key="sensor",
        translation_key="air_quality_sensor",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.get("sensor"),
    ),
    AirSmartSensorDescription(
        key="bypass_mode",
        translation_key="bypass_mode",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.get("bypass_mode"),
    ),
    AirSmartSensorDescription(
        key="vfirm",
        translation_key="firmware",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:chip",
        value_fn=lambda data: data.get("vfirm"),
    ),
    # --- Diagnostics from the Tasmota .../tele/.../STATE frame ---
    AirSmartSensorDescription(
        key=DATA_WIFI_SIGNAL,
        translation_key="wifi_signal",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.get(DATA_WIFI_SIGNAL),
    ),
    AirSmartSensorDescription(
        key=DATA_WIFI_RSSI,
        translation_key="wifi_rssi",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        icon="mdi:wifi",
        value_fn=lambda data: data.get(DATA_WIFI_RSSI),
    ),
    AirSmartSensorDescription(
        key=DATA_UPTIME,
        translation_key="uptime",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.get(DATA_UPTIME),
    ),
    AirSmartSensorDescription(
        key=DATA_HEAP,
        translation_key="free_memory",
        native_unit_of_measurement=UnitOfInformation.KILOBYTES,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        icon="mdi:memory",
        value_fn=lambda data: data.get(DATA_HEAP),
    ),
    AirSmartSensorDescription(
        key=DATA_MQTT_COUNT,
        translation_key="mqtt_connections",
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        icon="mdi:counter",
        value_fn=lambda data: data.get(DATA_MQTT_COUNT),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AirSmartConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the AirSmart sensors."""
    coordinator = entry.runtime_data
    async_add_entities(AirSmartSensor(coordinator, desc) for desc in SENSORS)


class AirSmartSensor(AirSmartEntity, SensorEntity):
    """A single telemetry value."""

    entity_description: AirSmartSensorDescription

    def __init__(self, coordinator, description: AirSmartSensorDescription) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.device_topic}_{description.key}"

    @property
    def native_value(self) -> Any:
        return self.entity_description.value_fn(self.coordinator.data)
