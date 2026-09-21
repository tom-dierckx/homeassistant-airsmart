"""State coordinator for the AirSmart Ventilation unit.

Subscribes (through Home Assistant's own MQTT client) to the unit's telemetry,
answers its keepalive ``ping`` and exposes helpers to publish ventilation-level
and other commands. The message shapes were worked out by observing the MQTT
traffic between an owned unit and its cloud on the local network.
"""

from __future__ import annotations

import json
import logging
import random
import re
import string
import time
from datetime import datetime, timedelta
from typing import Any

from homeassistant.components import mqtt
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import (
    BYPASS_CLOSE,
    BYPASS_OPEN,
    CMND_SERIALSEND_TOPIC,
    DATA_HEAP,
    DATA_MQTT_COUNT,
    DATA_SETPOINT,
    DATA_UPTIME,
    DATA_WIFI_RSSI,
    DATA_WIFI_SIGNAL,
    DOMAIN,
    ECHO_INT_KEYS,
    KEY_FILTER_COUNTER,
    LWT_ONLINE,
    STALE_AFTER_SECONDS,
    TELE_LWT_TOPIC,
    TELE_RESULT_TOPIC,
    TELE_STATE_TOPIC,
)

_LOGGER = logging.getLogger(__name__)

# The unit only reports the ventilation level and the "extra settings" as an echo
# right after they change - never unsolicited. Persist the last known values so
# the matching entities survive a restart/reload instead of coming back unknown.
_STORE_VERSION = 1
_STORE_SAVE_DELAY = 2  # seconds; debounces rapid changes

# Availability decays with the passage of time rather than on an incoming
# message, so without a periodic tick nothing would ever re-read `connected`
# once the unit went quiet - the staleness check could only run while messages
# were still arriving, which is exactly when it cannot trip.
_REFRESH_INTERVAL = timedelta(minutes=1)

# Telemetry fields that are reported as strings but represent floats.
_FLOAT_KEYS = ("freshair_temp", "extraction_temp")
# Telemetry fields reported as integers.
_INT_KEYS = (
    "sensor",
    "q_supply",
    "q_blowoff",
    "pwm_supply",
    "pwm_blowoff",
    "alarm1",
    "alarm2",
    "warning",
    "frot_protect_unbal",
    "frost_protect_inlet_off",
    "frostprotect_status",
    "bypass_status",
    "bypass_in_manual",
    "bypass_mode",
)
_STR_KEYS = ("vfirm",)
_ALL_STAT_KEYS = _FLOAT_KEYS + _INT_KEYS + _STR_KEYS

# Best-effort salvage for the occasional corrupt/truncated telemetry string the
# ESP emits.
_SALVAGE_RE = re.compile(r'\\?"?(\w+)\\?"?\s*:\s*\\?"?([\d.]+)')


def settings_store(hass: HomeAssistant, device_topic: str) -> Store[dict[str, int]]:
    """Per-device store of remembered settings, keyed the same way everywhere."""
    return Store(hass, _STORE_VERSION, f"{DOMAIN}.{device_topic}")


def _random_id(length: int = 32) -> str:
    """Random request id, matching the 32-char id the vendor app uses."""
    alphabet = string.ascii_letters + string.digits
    return "".join(random.choice(alphabet) for _ in range(length))


class AirSmartClient(DataUpdateCoordinator[dict[str, Any]]):
    """Subscribes to the unit over MQTT and holds its last known state."""

    def __init__(
        self,
        hass: HomeAssistant,
        *,
        topic_prefix: str,
        device_topic: str,
    ) -> None:
        super().__init__(
            hass, _LOGGER, name=DOMAIN, update_interval=_REFRESH_INTERVAL
        )
        self.device_topic = device_topic
        self._tele_topic = TELE_RESULT_TOPIC.format(
            prefix=topic_prefix, device=device_topic
        )
        self._cmnd_topic = CMND_SERIALSEND_TOPIC.format(
            prefix=topic_prefix, device=device_topic
        )
        self._lwt_topic = TELE_LWT_TOPIC.format(
            prefix=topic_prefix, device=device_topic
        )
        self._state_topic = TELE_STATE_TOPIC.format(
            prefix=topic_prefix, device=device_topic
        )

        self.data = {}
        self._device_online: bool | None = None
        self._last_message_at = 0.0
        self._boot_time: datetime | None = None
        self._unsubs: list[Any] = []
        self._store = settings_store(hass, device_topic)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    async def async_start(self) -> None:
        """Seed remembered settings, then subscribe through HA's MQTT client."""
        if stored := await self._store.async_load():
            self.data = {
                **self.data,
                **{k: v for k, v in stored.items() if v is not None},
            }
        self._unsubs = [
            await mqtt.async_subscribe(self.hass, self._tele_topic, self._on_tele, 1),
            await mqtt.async_subscribe(self.hass, self._lwt_topic, self._on_lwt, 1),
            await mqtt.async_subscribe(self.hass, self._state_topic, self._on_state, 1),
        ]

    async def async_stop(self) -> None:
        """Drop the MQTT subscriptions and flush remembered settings."""
        while self._unsubs:
            self._unsubs.pop()()
        await self._store.async_save(self._persistable())

    async def _async_update_data(self) -> dict[str, Any]:
        # Nothing to poll - the state arrives over MQTT. The periodic refresh
        # exists so entities re-read `available`; see _REFRESH_INTERVAL.
        return self.data

    def _persistable(self) -> dict[str, int]:
        """The subset of state worth remembering across restarts."""
        return {
            key: self.data[key]
            for key in ECHO_INT_KEYS
            if self.data.get(key) is not None
        }

    @callback
    def _remember(self) -> None:
        """Debounced save of the remembered settings."""
        self._store.async_delay_save(self._persistable, _STORE_SAVE_DELAY)

    # ------------------------------------------------------------------
    # Availability
    # ------------------------------------------------------------------
    @property
    def connected(self) -> bool:
        """True while MQTT is up, the device's LWT is not Offline and telemetry
        is fresh."""
        if not mqtt.is_connected(self.hass) or self._device_online is False:
            return False
        if not self._last_message_at:
            return True  # subscribed, waiting for the first telemetry frame
        return (time.monotonic() - self._last_message_at) < STALE_AFTER_SECONDS

    # ------------------------------------------------------------------
    # Commands
    # ------------------------------------------------------------------
    async def async_set_level(self, level: int) -> None:
        """Set the ventilation setpoint (0 = Low ... 3 = Boost)."""
        await self.async_set_setting(DATA_SETPOINT, int(level))

    async def async_set_setting(self, key: str, value: int) -> None:
        """Publish {"payload":{<key>:<value>}} and mirror it locally.

        Covers ``setpoint`` and the "extra settings": ``setpoint_timer_boost``,
        ``setpoint_low`` / ``_medium`` / ``_high`` / ``_boost`` and
        ``filter_counter``.
        """
        await self._publish({"payload": {key: int(value)}, "id": _random_id()})
        self.async_set_updated_data({**self.data, key: int(value)})
        self._remember()

    async def async_reset_filter(self) -> None:
        """Reset the clean-filter timer (write filter_counter = 0)."""
        await self.async_set_setting(KEY_FILTER_COUNTER, 0)

    async def async_sync_clock(self) -> None:
        """Push Home Assistant's wall clock to the unit's RTC."""
        now = dt_util.now()
        await self._publish(
            {
                "payload": {
                    "time": {
                        "year": now.year % 100,
                        "month": now.month,
                        "mday": now.day,
                        "hour": now.hour,
                        "min": now.minute,
                        "sec": now.second,
                    }
                },
                "id": _random_id(),
            }
        )

    async def async_set_bypass(self, open_bypass: bool) -> None:
        """Open or close the summer bypass."""
        command = BYPASS_OPEN if open_bypass else BYPASS_CLOSE
        await self._publish(
            {"payload": {"commands": command}, "id": _random_id()}
        )

    async def _publish(self, payload: dict[str, Any]) -> None:
        await mqtt.async_publish(
            self.hass, self._cmnd_topic, json.dumps(payload), qos=0
        )

    # ------------------------------------------------------------------
    # MQTT message handlers (run on the event loop)
    # ------------------------------------------------------------------
    @callback
    def _on_lwt(self, msg: mqtt.ReceiveMessage) -> None:
        self._device_online = str(msg.payload).strip() == LWT_ONLINE
        _LOGGER.debug("AirSmart LWT: %s", msg.payload)
        self.async_update_listeners()

    @callback
    def _on_state(self, msg: mqtt.ReceiveMessage) -> None:
        """Diagnostic values from the Tasmota .../tele/.../STATE frame.

        Deliberately not treated as liveness: these come from the ESP and keep
        arriving even when the ventilation unit behind it has gone silent.
        """
        try:
            body = json.loads(msg.payload)
        except ValueError:
            return
        wifi = body.get("Wifi") or {}
        updates: dict[str, Any] = {}
        if (signal := wifi.get("Signal")) is not None:
            updates[DATA_WIFI_SIGNAL] = _to_int(signal)
        if (rssi := wifi.get("RSSI")) is not None:
            updates[DATA_WIFI_RSSI] = _to_int(rssi)
        if (heap := body.get("Heap")) is not None:
            updates[DATA_HEAP] = _to_int(heap)
        if (count := body.get("MqttCount")) is not None:
            updates[DATA_MQTT_COUNT] = _to_int(count)
        if (uptime := body.get("UptimeSec")) is not None and (
            secs := _to_int(uptime)
        ) is not None:
            # Report as a stable boot timestamp; only move it if it drifts by
            # more than a minute so we do not churn the state on every frame.
            boot = (dt_util.utcnow() - timedelta(seconds=secs)).replace(microsecond=0)
            if self._boot_time is None or abs(
                (boot - self._boot_time).total_seconds()
            ) > 60:
                self._boot_time = boot
            updates[DATA_UPTIME] = self._boot_time
        if updates:
            self.async_set_updated_data({**self.data, **updates})

    @callback
    def _on_tele(self, msg: mqtt.ReceiveMessage) -> None:
        try:
            body = json.loads(msg.payload)
        except ValueError:
            _LOGGER.debug("Ignoring non-JSON telemetry: %s", str(msg.payload)[:120])
            return

        serial_received = body.get("SerialReceived")
        if serial_received is None:
            # e.g. {"SerialSend":"Done"} acknowledgements - the ESP talking back,
            # not the unit, so this is not liveness either.
            return

        # Past this point the frame came over the serial link from the unit.
        self._last_message_at = time.monotonic()

        if isinstance(serial_received, str):
            self._handle_serial_string(serial_received)
            return

        if not isinstance(serial_received, dict):
            return

        message = serial_received.get("message")
        if isinstance(message, str):
            # {"message":"ACK","id":...} or {"message":"ERROR writing object","id":"NULL"}
            if message.startswith("ERROR"):
                _LOGGER.warning(
                    "AirSmart rejected a command (id=%s): %s",
                    serial_received.get("id"),
                    message,
                )
            return

        payload = serial_received.get("payload")
        if isinstance(payload, dict):
            if payload.get("message") == "ping":
                self.hass.async_create_task(
                    self._answer_ping(serial_received.get("id"))
                )
                return
            if "message" in payload:
                return
            if "freshair_temp" in payload:
                self._update_stats(payload)
                return
            # State echoes the unit sends after a value changes (from us or the
            # app). One or more keys per frame, e.g.
            #   {"SerialReceived":{"payload":{"setpoint":1},"id":807625715}}
            #   {"SerialReceived":{"payload":{"setpoint_medium":31,"setpoint_high":36},"id":...}}
            # The periodic stats blob does *not* carry any of these, so the echo
            # is the only feedback we get.
            updates = {
                key: _to_int(value)
                for key, value in payload.items()
                if key in ECHO_INT_KEYS
            }
            if updates:
                self.async_set_updated_data({**self.data, **updates})
                self._remember()
                return
        # {"debug_rf": ...} frames land here; nothing to do.

    def _handle_serial_string(self, text: str) -> None:
        """Deal with the malformed telemetry strings the ESP sometimes sends."""
        if "debug_rf" in text or "pwm_supply" not in text:
            return
        salvaged: dict[str, Any] = {}
        for key, value in _SALVAGE_RE.findall(text):
            if key not in _ALL_STAT_KEYS:
                continue
            salvaged[key] = value
        if salvaged:
            _LOGGER.debug("Salvaged stats from corrupt frame: %s", salvaged)
            self._update_stats(salvaged)

    async def _answer_ping(self, msg_id: Any) -> None:
        await self._publish({"payload": {"message": "answerPing"}, "id": msg_id})

    def _update_stats(self, payload: dict[str, Any]) -> None:
        parsed: dict[str, Any] = dict(self.data)
        for key in _FLOAT_KEYS:
            if key in payload:
                parsed[key] = _to_float(payload[key])
        for key in _INT_KEYS:
            if key in payload:
                parsed[key] = _to_int(payload[key])
        for key in _STR_KEYS:
            if key in payload:
                parsed[key] = str(payload[key])
        self.async_set_updated_data(parsed)


def _to_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_int(value: Any) -> int | None:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None
