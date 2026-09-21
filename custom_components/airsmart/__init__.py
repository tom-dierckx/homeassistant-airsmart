"""The AirSmart Ventilation integration."""

from __future__ import annotations

from homeassistant.components import mqtt
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import (
    CONF_DEVICE_TOPIC,
    CONF_TOPIC_PREFIX,
    CONFIG_ENTRY_VERSION,
    PLATFORMS,
)
from .coordinator import AirSmartClient, settings_store

type AirSmartConfigEntry = ConfigEntry[AirSmartClient]


async def async_setup_entry(hass: HomeAssistant, entry: AirSmartConfigEntry) -> bool:
    """Set up AirSmart Ventilation from a config entry."""
    if not await mqtt.async_wait_for_mqtt_client(hass):
        raise ConfigEntryNotReady("MQTT integration is not available yet")

    client = AirSmartClient(
        hass,
        topic_prefix=entry.data[CONF_TOPIC_PREFIX],
        device_topic=entry.data[CONF_DEVICE_TOPIC],
    )
    await client.async_start()

    entry.runtime_data = client
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: AirSmartConfigEntry) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await entry.runtime_data.async_stop()
    return unloaded


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate old entries.

    v1 stored broker host/port/username/password; v2 rides HA's MQTT client and
    keeps only the Tasmota topic identity.
    """
    if entry.version > CONFIG_ENTRY_VERSION:
        return False
    if entry.version < CONFIG_ENTRY_VERSION:
        device_topic = entry.data.get(CONF_DEVICE_TOPIC, "")
        hass.config_entries.async_update_entry(
            entry,
            data={
                CONF_TOPIC_PREFIX: entry.data.get(CONF_TOPIC_PREFIX, ""),
                CONF_DEVICE_TOPIC: device_topic,
            },
            unique_id=device_topic or entry.unique_id,
            version=CONFIG_ENTRY_VERSION,
        )
    return True


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Delete the remembered-settings store when the entry is removed."""
    device_topic = entry.data.get(CONF_DEVICE_TOPIC)
    if device_topic:
        await settings_store(hass, device_topic).async_remove()
