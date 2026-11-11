# EasyWallbox → ESPHome

Control the EasyWallbox charger (eSolutions Charging) via Bluetooth using ESPHome on an ESP32‑S3.

This project integrates EasyWallbox into ESPHome and Home Assistant through a Bluetooth Low Energy (BLE) connection. It exposes charging controls, confirmed settings, current charging measurements and diagnostics.

> **Development version:** This README describes the firmware on the `sviluppo-test` branch. The latest command-queue, recovery, telemetry and entity-cleanup changes still require compilation and testing on a physical ESP32. The stable `main` branch has not been updated.

---

##  Requirements

- ESP32‑S3 development board (the YAML is configured for an 8 MB flash ESP32‑S3 and ESP-IDF)
- EasyWallbox (eSolutions Charging), accessible over BLE
- A Wi-Fi network and Home Assistant with the ESPHome integration
- **An installed and enabled DPM system for the Start-Stop behavior described below.** This firmware currently pauses by setting the DPM limit to zero. It is **not yet a supported solution for charging control with DPM disabled or without a DPM meter**.

---

##  Important Notes

The EasyWallbox supports **one active BLE controller connection at a time**. Disconnect the manufacturer's app before using ESPHome; simultaneous connections can interfere with each other.

**Electrical safety:** the DPM protects against exceeding the configured overall household power threshold only when the appropriate meter is installed and DPM is enabled and correctly configured. Disabling DPM can cause overloads. ESPHome and Home Assistant are *not* substitutes for electrical protections.

You need two parameters from your charger:

- **Bluetooth MAC address**  
- **4-digit BLE authentication PIN**, distinct from the BLE pairing passkey (the firmware currently supplies numeric passkey `1234` for pairing).

---

##  How to Retrieve the PIN

1. Follow the manufacturer's safety instructions. If access to a QR label requires opening an electrical enclosure, isolate power and have qualified personnel perform that work.
2. Scan the charger's identification QR code with a QR reader.
3. Find the `A:` field in the QR payload: it is the BLE authentication PIN. The `P:` field, if present, is the separate pairing passkey.
4. Enter the BLE authentication PIN as `wallbox_pin`. Do **not** assume that the last four digits of the entire QR payload are always the PIN.

---

##  How to Retrieve the MAC Address

### From Home Assistant
- Settings → Devices & Services → Bluetooth  
- Scan for nearby devices  
- Look for a device named similar to *EasyWallbox* or *EW‑xxxx*

### From Linux
- Bash terminal
- sudo hcitool lescan 
- Look for a device named similar to *EasyWallbox* or *EW‑xxxx*

### From Windows
- Settings → Bluetooth & Devices → Add Device → Bluetooth 
- Scan and identify the EasyWallbox 
- Or use Bluetooth LE Explorer (Microsoft Store), which shows MAC addresses reliably

### From any Android APP
- Use any Bluetooth scanner app (e.g., BLE Scanner) to find the device and read its MAC address.


---

## Installation

1. Copy [wallbox.yaml](wallbox.yaml) to your ESPHome configuration directory (or create a new ESPHome device and paste the YAML).
2. Edit the `substitutions` section at the start of the file. The current configuration uses:

~~~yaml
substitutions:
  wifi_ssid: "YOUR SSID"
  wifi_password: "YOUR PASSWORD"
  api_key: "YOURKEY"
  wallbox_mac: "xx:xx:xx:xx:xx:xx"
  wallbox_pin: "XXXX"
  dpm_default: "6"
  max_charge_kw: "6"
  max_house_kw: "6"
  poll_interval_s: "30"
  telemetry_stale_s: "100"
~~~

| Setting | Meaning |
|---|---|
| `wifi_ssid` / `wifi_password` | Wi-Fi credentials |
| `api_key` | **Required** valid ESPHome native API encryption key (base64 encoded); do not leave the placeholder |
| `wallbox_mac` | BLE MAC address of your charger |
| `wallbox_pin` | BLE authentication PIN from the charger QR label (`A:` field) |
| `dpm_default` | Fallback household + vehicle power limit in kW when no previously valid DPM setting is available |
| `max_charge_kw` | Maximum value of the `Charge power` Home Assistant slider, in kW |
| `max_house_kw` | Maximum value of the `Home limit -DPM-` slider, in kW |
| `poll_interval_s` | Periodic BLE telemetry polling interval in seconds: **30** by default |
| `telemetry_stale_s` | Seconds since the last valid AD telemetry response before readings are marked stale: **100** by default |

Choose the power limits based on the charger, installed wiring and supply contract. These UI limits do **not** replace proper electrical protection.

3. Validate/compile in ESPHome and install on the ESP32-S3. Once the device is online, add it to Home Assistant using the ESPHome integration.


The ESPHome device uses the configured native encrypted API. The encryption key must be valid for both the ESPHome device and the Home Assistant connection.

---

## Features

### Charging control — DPM-enabled mode

The current Start-Stop logic **requires DPM to be installed and enabled**.

- **Stop / Pause:** writes `$EEP,WRITE,IDX,158,0` to set the DPM limit to **0 A**. This is the established method used by this project to pause a session without unplugging the car.
- **Start / Resume:** restores the previously remembered valid DPM limit. If none is available, the firmware uses `dpm_default` (in kW).
- **`Charge power` slider:** changes the vehicle user-current limit, using EEPROM index `174`.
- **`Home limit -DPM-` slider:** changes the total household + vehicle DPM threshold, using EEPROM index `158`. When the Start-Stop switch is OFF, its desired value is remembered for the next resume rather than immediately restarting the session.
- **The DPM-enable setting itself is not controlled by a switch in this firmware.** The `DPM Active` entity is a **read-only** diagnostic.

**Why not use native charge STOP / START commands?** On the project owner's wallbox, native `$CMD,CHARGE,STOP,0` prevents a subsequent native START from resuming the same plugged-in session without physically disconnecting/reconnecting the cable. Therefore the firmware deliberately uses DPM = 0 A instead. Do not substitute the native commands in automations assuming equivalent behavior.

**Do not turn off DPM while relying on this Start-Stop switch.** With DPM disabled or without the meter, a zero DPM limit may no longer pause charging. This version does not provide a tested alternative control mode for those installations.

### Requested state versus confirmed state

The `Charge power`, `Home limit -DPM-` and `Start-Stop` controls update the Home Assistant interface immediately after a request. This is **not an acknowledgement** from the charger.

Use `Power set`, `Limit house power set -DPM-`, `Charge Enabled`, and `BLE Command Status` to check the subsequently reported state. In particular, `Charge Enabled` means **the last confirmed DPM limit is greater than zero**, not that the vehicle is drawing current. The separate `Charging` sensor describes the charger-reported charging state.

The BLE writer serializes commands. Sliders have an **800 ms debounce** and obsolete queued slider writes can be skipped before transmission. If a write has no matching response within **10 seconds**, the firmware attempts to read back the corresponding EEPROM register instead of blindly repeating the write. Errors/disconnections and a real charging session still need to be validated with the latest development firmware.

### Periodic telemetry and stale data

- `$DATA,READ,AD` is requested approximately every **30 seconds**, regardless of whether a vehicle is charging. The request is deferred while the BLE command writer is busy, so the interval can be longer.
- `Refresh Data` manually requests EEPROM index `174`, index `158`, and an AD telemetry frame.
- After a previously valid AD frame, if more than **100 seconds** pass without another valid AD frame, `Telemetry Fresh` changes to OFF and the affected measurements are invalidated. BLE disconnection also invalidates affected measurements.
- Staleness detection changes **only the reported data**: it does not intentionally stop charging or change DPM settings.

### Home Assistant entities (26 exposed)

The following are the **display names** from ESPHome; the actual Home Assistant `entity_id` may differ. One additional BLE receiver, `wallbox_rx`, is internal and is not an exposed entity.

#### Controls (5)

| Name | Purpose |
|---|---|
| `Charge power` | Requested maximum vehicle charging power (kW) |
| `Home limit -DPM-` | Requested household + EV DPM threshold (kW) |
| `Start-Stop` | Resume or pause using the DPM-limit method |
| `Refresh Data` | Ask the charger for current settings and AD telemetry |
| `Restart ESP32` | Restart the ESP32 device |

#### States (8)

| Name | Purpose |
|---|---|
| `Connection` | BLE authenticated/connected status |
| `Charge State` | Charger state, e.g. Cable Unplugged, Pause, Vehicle ready, Charging, Error |
| `Charging` | Whether the charger reports charging state |
| `Charge Enabled` | Whether the confirmed DPM limit is nonzero |
| `Car Connected` | Whether the charger detects a connected vehicle |
| `DPM Active` | Whether the wallbox reports DPM enabled (read-only) |
| `Wallbox Fault` | Error indication from the wallbox telemetry |
| `Telemetry Fresh` | Whether AD telemetry is currently considered fresh |

#### Measurements (10)

| Name | Purpose |
|---|---|
| `Charging Current` | Measured vehicle charging current (A) |
| `Charging Power` | Measured vehicle charging power (kW) |
| `House total power -DPM-` | Total power derived from the wallbox's DPM current reading (kW) |
| `Session Energy` | Session energy reported by the wallbox (kWh) |
| `Session Duration` | Session charging duration (minutes) |
| `Power set` | Confirmed vehicle power limit (kW) |
| `Limit house power set -DPM-` | Confirmed DPM limit (kW, can be 0 while paused) |
| `Control Pilot Voltage` | Positive Control Pilot signalling voltage (V) |
| `Pilot Advertised Current` | Maximum current offered to the car by PWM signalling (A), if a valid PWM signal is present |
| `Safe Current Limit` | Charger-reported safety current limit (A) |

#### Diagnostics (3)

| Name | Purpose |
|---|---|
| `Z-RAW Debug` | Raw BLE response text for troubleshooting (the displayed value is cleared after a short delay on AD updates) |
| `BLE Command Status` | Pending, confirmed, verification or failure status of a command |
| `Uptime` | ESP32 uptime, in hours |

The 12 redundant/low-value sensor definitions (including Voltage, PWM Raw, Duty Cycle, Contactor Closed and ESP32 free ram) were removed from the firmware. The raw protocol message remains available to the parser; removing these sensors does not change the amount of BLE telemetry requested.

### Understanding Control Pilot Voltage

The **Control Pilot (CP)** is a signalling contact between the charger and the car. This is **not** the household 230 V supply voltage and **not** battery voltage. It helps diagnose why a charge has not started.

| Typical positive CP voltage | Indicative interpretation |
|---|---|
| ~12 V | No vehicle connected (state A) |
| ~9 V | Vehicle connected, not yet requesting energy (state B) |
| ~6 V | Vehicle requesting charging power (state C) |
| ~3 V | Special ventilation-required state (state D; uncommon) |

These are approximate nominal values, not calibrated thresholds. For everyday dashboards and automations, prefer `Car Connected`, `Charge State` and `Charging` over interpreting CP voltage directly.

The wallbox also signals the **maximum current it offers** through a PWM signal on CP. `Pilot Advertised Current` converts that signal to amperes when its duty cycle is valid. It is **not the actual current consumed**: compare it with `Charging Current`. The wallbox protocol uses a raw PWM value of `1000` to indicate **no PWM**, not 100% charging.

---

### Manual Command Service (Advanced Users)

The ESPHome native API exposes a `send_command` action that forwards an arbitrary command string to the BLE queue. The latest raw response is exposed as **`Z-RAW Debug`**, not a sensor named "Raw".

**Advanced users only.** Manual commands bypass the normal UI workflow and may change persistent EEPROM settings or disable DPM overload management. They are not required for standard charging control. The commands below are protocol examples retained from the original README; not every manual reply format has been tested with the new BLE response matcher. A command timeout does not by itself prove the wallbox rejected a write.

Use the normal sliders and Start-Stop control for everyday operation. **Never issue a DPM OFF command while relying on DPM for household load protection.**

### EEPROM / data commands

- READ ALARMS → $EEP,READ,AL,{alarmnum}
- READ MANUFACTURING → $EEP,READ,MF
- READ CHARGING SESSIONS → $EEP,READ,SL,{sessionnum}
- READ SETTINGS → $EEP,READ,ST
- READ APP DATA → $DATA,READ,AD
- READ HW SETTINGS → $DATA,READ,HS
- READ SUPPLY VOLTAGE → $DATA,READ,SV

### Write commands — potentially unsafe

- SET USER LIMIT → $EEP,WRITE,IDX,174,{limit}
- SET DPM LIMIT → $EEP,WRITE,IDX,158,{limit}
- SET DPM OFF → $EEP,WRITE,IDX,178,0
- SET DPM ON → $EEP,WRITE,IDX,178,1

### Read commands

- GET USER LIMIT → $EEP,READ,IDX,174
- GET DPM LIMIT → $EEP,READ,IDX,158
- GET SAFE LIMIT → $EEP,READ,IDX,156
- GET DPM STATUS → $EEP,READ,IDX,178

# 🍺 Support the Project

If you found this project useful and want to support my work, you can offer me a beer:

[![Buy Me a Beer](https://img.shields.io/badge/Buy%20Me%20a%20Beer-0070ba?style=for-the-badge&logo=paypal&logoColor=white)](https://paypal.me/PaoloFazari)


## Contributions
Contributions are welcome

## License
Released under the MIT License.

## 
**Thanks to the Ceppy's balcony for the inspiration** 
