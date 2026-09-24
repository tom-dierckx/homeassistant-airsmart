# AirSmart Ventilation for Home Assistant

I have an AirSmart / Ictus heat-recovery ventilation unit at home it 
comes with an ESP8266 that talks to `api.airsmart.pro`. This is a
Home Assistant integration that talks to it directly over MQTT on the local
network instead.

It controls the ventilation level and the summer bypass, exposes the
temperatures / airflow / alarms the unit reports, and answers the
keepalive "ping" the unit expects (if not it the unit goes offline).

## Heads up

This is all reverse engineered from watching the MQTT traffic between my own
unit and its cloud. There is no official API and no documentation. I am **not
affiliated with, endorsed by or supported by AirSmart or Ictus** - "AirSmart"
and "Ictus" are their trademarks and are used here only to say what device this
talks to.

It works on my unit (firmware `01.07.00`). Yours may behave
differently - the bypass direction in particular is not fully confirmed, see
[Known quirks](#known-quirks). Use at your own risk; poking a ventilation unit
over an unofficial protocol could in theory upset it or void a warranty.

## Requirements

- Home Assistant 2026.8 or newer
- The **MQTT integration** set up and connected to a broker (the *Mosquitto
  broker* add-on).
- Your AirSmart unit pointed at that same broker (next section).

## Getting the unit onto your broker

The unit ships pointed at `api.airsmart.pro` with MQTT credentials baked into
the firmware, and the Tasmota web UI is usually locked with a factory
`WebPassword`. You need to send it to a broker you control. You do **not** need
to know the factory password - you either make your broker accept it or you
replace it.

### What I did: read the credentials off the wire

The unit connects to `api.airsmart.pro` over plain MQTT on port 1883 - no TLS -
so the username and password sit in cleartext in the MQTT CONNECT packet. I ran
a packet capture on my router, filtered on the unit's traffic, and read the
user/pass straight out of the CONNECT packet (in Wireshark:
`mqtt.msgtype == 1`). Any capture point that sees the device's traffic works -
`tcpdump`/`tshark` on the router, a mirror port, or the broker box itself once
DNS points at it (the rejected login attempt still shows the creds).

Then:

1. Add the captured user/pass to your local broker's login list.
2. On your router / Pi-hole / AdGuard, make `api.airsmart.pro` resolve to your
   broker.
3. Point Home Assistant's MQTT integration at that same broker.

The nice part is that you never touch the device. Everything stays local - the
vendor cloud is not in the loop. And since `MqttHost` and `WebPassword` on the
unit are untouched, reverting is just deleting the DNS override: the unit
reconnects to the real cloud on its next try and the original apps work again,
no reflash or reconfig needed.

### Other options (untested)

These should work in theory, but **I haven't tried them** - if you do, let me
know how it goes.

**Anonymous broker + Tasmota fallback topic.** Redirect `api.airsmart.pro` to
your broker as above, but run the broker so it accepts the unknown login for a
minute (`allow_anonymous true`, no password file), power-cycle the unit, and
once it connects use Tasmota's fallback topic to take control:

```
cmnd/DVES_<clientid>_fb/WebPassword 0        # clears the UI lock
cmnd/DVES_<clientid>_fb/MqttHost <broker-ip> # optional: make it permanent
cmnd/DVES_<clientid>_fb/MqttUser  <user>
cmnd/DVES_<clientid>_fb/MqttPassword <pass>
```

The `<clientid>` shows up in the broker log when the unit connects
(`DVES_XXXXXX`). Afterwards you can turn broker auth back on. Unlike the capture
approach this changes settings on the device, so going back to the cloud means
undoing them.

Once it's on your broker it publishes a retained
`tasmota/discovery/<mac>/config` message and the integration can find it from
there.

## Install

### HACS

Add this repo as a custom repository (type *Integration*), install
**AirSmart Ventilation**, restart Home Assistant.

### Manual

Copy `custom_components/airsmart/` into your `config/custom_components/` folder
and restart.

## Add it in Home Assistant

- **Automatic** - once the unit is on the broker, HA shows a *Discovered ->
  AirSmart Ventilation* card. Click *Configure* and confirm.
- **Manually** - *Settings -> Devices & Services -> Add Integration ->
  AirSmart Ventilation*. It scans for units and gives you a dropdown. If nothing
  turns up it asks for two values from the discovery message: the leading part
  of `ft` (before `/%prefix%/`) and the value of `t`.

If you're coming from an older version that asked for broker host/credentials,
the config entry migrates itself and those fields go away.

## Options

| Entity | Notes |
| --- | --- |
| `select` – Ventilation level | Low / Medium / High / Boost. |
| `switch` – Bypass | Open / close the summer bypass. State polarity: see quirks. |
| `number` – Boost timer, and Low/Medium/High/Boost airflow % | Config values. These only change when you set them or the vendor app does. |
| `button` – Reset filter counter, Sync clock | Resets the clean-filter timer; pushes HA's time to the unit's clock. |
| `sensor` – fresh air & extraction temp, supply & exhaust airflow, fan PWM, air-quality sensor, bypass mode, firmware | The main telemetry. |
| `sensor` (diagnostic) – Wi-Fi signal, uptime, free memory, MQTT connections | Pulled from the Tasmota `STATE` message, disabled by default. |
| `binary_sensor` – Alarm 1/2, Warning, Frost protection, Bypass open, Bypass in manual | |

Availability follows the retained Tasmota last-will (`Online` / `Offline`).

## Known quirks

- **Bypass direction is not confirmed.** In the traffic I captured `close_bypass`
  was followed by `bypass_status: 1` and `open_bypass` by `0`, which would mean
  `1 == closed` - but on a warm day (bypass presumably open) it also read `1`.
  I have not used this setting and keep it on the state that it was.
- **Level and the config numbers only update after a change.** The unit sends
  these as an echo when they change and never just sends them, so right after a
  fresh install they read *unknown* until you change something. The
  last known values are written to `.storage/airsmart.<device>` so they survive
  restarts after that.
- **"Tasmota" device discovery** HA's own Tasmota discovery picks the
  ESP up from the same message and makes a seperate device with a `POWER`
  switch. That's the ESP's and I haven't touched it - ignore or disable
  it.

## Examples

[`examples/`](examples/) has automations you can copy into your own setup:

- [`ventilation_schedule.yaml`](examples/ventilation_schedule.yaml) - switches
  the level between Low and Medium based on a `schedule` helper (e.g. Medium
  during the day, Low overnight).

## Contributing

Captures contain credentials so please do not share them however if you can get more info related the bypass and bypass polarity that would be awesome (send in an issue).

## License

MIT, see [LICENSE](LICENSE).
