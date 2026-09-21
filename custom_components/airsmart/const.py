"""Constants for the AirSmart Ventilation integration."""

from __future__ import annotations

from homeassistant.const import Platform

DOMAIN = "airsmart"

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]

# Config entry keys (the integration rides Home Assistant's own MQTT client, so
# only the Tasmota topic identity is stored).
CONF_TOPIC_PREFIX = "topic_prefix"
CONF_DEVICE_TOPIC = "device_topic"

CONFIG_ENTRY_VERSION = 2

# Tasmota discovery: retained JSON at tasmota/discovery/<mac>/config. We match a
# unit by its device name / module string.
TASMOTA_DISCOVERY_TOPIC = "tasmota/discovery/+/config"
AIRSMART_NAME_HINT = "airsmart"
AIRSMART_MODULE_HINT = "0FU"

# The device firmware is Tasmota based. The "full topic" prefix and the device
# topic together build the concrete MQTT topics, e.g.
#   <prefix>/tele/<device>/RESULT
#   <prefix>/cmnd/<device>/serialsend
TELE_RESULT_TOPIC = "{prefix}/tele/{device}/RESULT"
CMND_SERIALSEND_TOPIC = "{prefix}/cmnd/{device}/serialsend"
# Tasmota last-will (retained "Online" / "Offline") and device telemetry.
TELE_LWT_TOPIC = "{prefix}/tele/{device}/LWT"
TELE_STATE_TOPIC = "{prefix}/tele/{device}/STATE"
LWT_ONLINE = "Online"

# Diagnostic values lifted from the Tasmota .../tele/.../STATE frame. Namespaced
# so they cannot collide with the ventilation telemetry keys.
DATA_WIFI_SIGNAL = "dev_wifi_signal"
DATA_WIFI_RSSI = "dev_wifi_rssi"
DATA_UPTIME = "dev_uptime"
DATA_HEAP = "dev_heap"
DATA_MQTT_COUNT = "dev_mqtt_count"

# The setpoint field (0-3) selects one of four named levels. The unit always
# runs - there is no "off"; setpoint 0 is "Low". The names line up with the
# setpoint_low / setpoint_medium / setpoint_high / setpoint_boost config keys.
VENTILATION_LEVELS = ["low", "medium", "high", "boost"]

# Bypass commands
BYPASS_OPEN = "open_bypass"
BYPASS_CLOSE = "close_bypass"

# Keepalive: if we have not heard from the unit for this long we consider it
# unavailable even while the MQTT socket stays connected.
STALE_AFTER_SECONDS = 15 * 60

# Data keys kept in the coordinator payload.
DATA_SETPOINT = "setpoint"

# "Extra settings" the unit accepts on the serialsend topic as
# {"payload":{<key>:<int>},"id":"<rand32>"} and echoes back on tele/RESULT as
# {"SerialReceived":{"payload":{<key>:<int>},"id":<int>}}.
#
#   setpoint_timer_boost  how long Boost runs before dropping back (minutes)
#   setpoint_low/medium/high/boost   fan intensity for each level; 0 = factory default
#   filter_counter        write 0 to reset the clean-filter timer
KEY_BOOST_TIMER = "setpoint_timer_boost"
KEY_FILTER_COUNTER = "filter_counter"
LEVEL_SETPOINT_KEYS = (
    "setpoint_low",
    "setpoint_medium",
    "setpoint_high",
    "setpoint_boost",
)

# Integer keys the unit echoes on tele/RESULT that we mirror into the coordinator
# payload so the matching entities can show the current value.
ECHO_INT_KEYS = (DATA_SETPOINT, KEY_BOOST_TIMER, KEY_FILTER_COUNTER, *LEVEL_SETPOINT_KEYS)
