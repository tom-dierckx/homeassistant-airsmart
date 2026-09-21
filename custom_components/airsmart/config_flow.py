"""Config flow for the AirSmart Ventilation integration.

The integration uses Home Assistant's own MQTT client, so there is nothing to
configure beyond which unit to talk to. Units are found from the retained
Tasmota discovery message; manual entry is the fallback.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import voluptuous as vol

from homeassistant.components import mqtt
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.core import callback
from homeassistant.helpers.service_info.mqtt import MqttServiceInfo

from .const import (
    AIRSMART_MODULE_HINT,
    AIRSMART_NAME_HINT,
    CONF_DEVICE_TOPIC,
    CONF_TOPIC_PREFIX,
    CONFIG_ENTRY_VERSION,
    DOMAIN,
    TASMOTA_DISCOVERY_TOPIC,
)

_LOGGER = logging.getLogger(__name__)

_SCAN_SECONDS = 3
_MANUAL = "__manual__"


def _parse_discovery(payload: Any) -> dict[str, str] | None:
    """Turn a tasmota/discovery/<mac>/config payload into topic identity."""
    try:
        data = json.loads(payload)
    except (ValueError, TypeError):
        return None
    if not isinstance(data, dict):
        return None
    topic = data.get("t")
    full_topic = data.get("ft", "")
    if not topic or "%prefix%" not in full_topic or "%topic%" not in full_topic:
        return None
    name = str(data.get("dn") or "")
    model = str(data.get("md") or "")
    if AIRSMART_NAME_HINT not in name.lower() and not model.upper().startswith(
        AIRSMART_MODULE_HINT
    ):
        return None
    return {
        "prefix": full_topic.split("%prefix%", 1)[0].rstrip("/"),
        "device_topic": str(topic),
        "name": name or f"AirSmart {topic}",
        "model": model,
    }


class AirSmartConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for AirSmart Ventilation."""

    VERSION = CONFIG_ENTRY_VERSION

    def __init__(self) -> None:
        self._discovered: dict[str, str] = {}
        self._found: dict[str, dict[str, str]] | None = None

    # ------------------------------------------------------------------
    # Push discovery from the retained Tasmota discovery message
    # ------------------------------------------------------------------
    async def async_step_mqtt(
        self, discovery_info: MqttServiceInfo
    ) -> ConfigFlowResult:
        """Handle a unit announced via MQTT discovery."""
        info = _parse_discovery(discovery_info.payload)
        if info is None:
            return self.async_abort(reason="not_airsmart")
        await self.async_set_unique_id(info["device_topic"])
        self._abort_if_unique_id_configured(
            updates={CONF_TOPIC_PREFIX: info["prefix"]}
        )
        self._discovered = info
        self.context["title_placeholders"] = {"name": info["name"]}
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm setup of a discovered unit."""
        if user_input is not None:
            return self._create_entry(self._discovered)
        return self.async_show_form(
            step_id="confirm",
            description_placeholders={
                "name": self._discovered["name"],
                "model": self._discovered.get("model") or "?",
                "device_topic": self._discovered["device_topic"],
            },
        )

    # ------------------------------------------------------------------
    # User-initiated
    # ------------------------------------------------------------------
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Let the user pick a discovered unit, or fall back to manual entry."""
        self.context.setdefault("title_placeholders", {"name": "AirSmart Ventilation"})
        if not await mqtt.async_wait_for_mqtt_client(self.hass):
            return self.async_abort(reason="mqtt_unavailable")

        if self._found is None:
            self._found = await self._async_scan()
        if not self._found:
            return await self.async_step_manual()

        if user_input is not None:
            choice = user_input[CONF_DEVICE_TOPIC]
            if choice == _MANUAL:
                return await self.async_step_manual()
            info = self._found[choice]
            await self.async_set_unique_id(
                info["device_topic"], raise_on_progress=False
            )
            self._abort_if_unique_id_configured()
            return self._create_entry(info)

        options = {
            dev: f"{i['name']} ({dev})" for dev, i in self._found.items()
        }
        options[_MANUAL] = "Enter topics manually"
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required(CONF_DEVICE_TOPIC): vol.In(options)}
            ),
        )

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Enter the Tasmota full-topic prefix and device topic by hand."""
        self.context.setdefault("title_placeholders", {"name": "AirSmart Ventilation"})
        if user_input is not None:
            prefix = user_input[CONF_TOPIC_PREFIX].strip().strip("/")
            device = user_input[CONF_DEVICE_TOPIC].strip().strip("/")
            await self.async_set_unique_id(device, raise_on_progress=False)
            self._abort_if_unique_id_configured()
            return self._create_entry(
                {
                    "prefix": prefix,
                    "device_topic": device,
                    "name": f"AirSmart {device}",
                }
            )
        return self.async_show_form(
            step_id="manual",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_TOPIC_PREFIX): str,
                    vol.Required(CONF_DEVICE_TOPIC): str,
                }
            ),
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    async def _async_scan(self) -> dict[str, dict[str, str]]:
        """Collect retained Tasmota discovery messages for a few seconds."""
        found: dict[str, dict[str, str]] = {}

        @callback
        def _on_message(msg: mqtt.ReceiveMessage) -> None:
            if info := _parse_discovery(msg.payload):
                found[info["device_topic"]] = info

        unsub = await mqtt.async_subscribe(
            self.hass, TASMOTA_DISCOVERY_TOPIC, _on_message
        )
        try:
            await asyncio.sleep(_SCAN_SECONDS)
        finally:
            unsub()

        configured = {entry.unique_id for entry in self._async_current_entries()}
        return {
            dev: info for dev, info in found.items() if dev not in configured
        }

    def _create_entry(self, info: dict[str, str]) -> ConfigFlowResult:
        return self.async_create_entry(
            title=info.get("name") or f"AirSmart {info['device_topic']}",
            data={
                CONF_TOPIC_PREFIX: info["prefix"],
                CONF_DEVICE_TOPIC: info["device_topic"],
            },
        )
