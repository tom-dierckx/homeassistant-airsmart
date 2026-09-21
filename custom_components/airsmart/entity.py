"""Base entity for the AirSmart Ventilation integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import AirSmartClient


class AirSmartEntity(CoordinatorEntity[AirSmartClient]):
    """Common base: device info + MQTT-aware availability."""

    _attr_has_entity_name = True

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.device_topic)},
            name="AirSmart Ventilation",
            manufacturer="AirSmart / Ictus",
            model="ESP MQTT bridge",
            sw_version=self.coordinator.data.get("vfirm"),
        )

    @property
    def available(self) -> bool:
        return super().available and self.coordinator.connected
