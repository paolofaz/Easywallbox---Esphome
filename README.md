# EasyWallbox → ESPHome

Control the EasyWallbox charger (eSolutions Charging) via Bluetooth using ESPHome on an ESP32‑S3.

This project integrates the EasyWallbox into ESPHome, enabling full Bluetooth control and real‑time monitoring directly from Home Assistant.

---

##  Requirements

- ESP32‑S3 development board  
- EasyWallbox (eSolutions Charging) with DPM sensor

---

##  Important Notes

The EasyWallbox can connect to **only one device at a time**.  
You must uninstall or disable the official smartphone app before pairing it with ESPHome.

You need two parameters from your charger:

- **Bluetooth MAC address**  
- **4‑digit PIN** (not the default 1234, although 1234 is still required for the initial handshake)

---

##  How to Retrieve the PIN

1. Remove the front cover of the EasyWallbox.  
2. Scan the QR code underneath using any QR scanner app.  
3. The result will be a long alphanumeric string.  
4. The **last 4 digits** are the Bluetooth PIN.

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

##  Installation

Copy wallbox.yaml into your ESPHome configuration directory or copy and paste the code in a new project making the following changes

At the top of the YAML file you will find:

```
substitutions:
  wallbox_mac: "xx:xx:xx:xx:xx:xx" #Wallbox bluetooth MAC ADRRESS
  wallbox_pin: "XXXX" #Wallbox pin bluetooth (scan qr code, last 4 digit)
  dpm_default: 4.8  #Default KW home DPM 
```
Replace with:

1) wallbox_mac → your EasyWallbox Bluetooth MAC
2) wallbox_pin → the 4‑digit PIN
3) dpm_default → maximum power supported by your installation - Example: 4.8 = 4.8 kW - This is the base DPM value (modifiable later from Home Assistant)

Also update:

wifi ssid, wifi password, ota password (optional), api encryption.key (optional)

---

## Features

### Charging Control

- Start and Pause charging
- Set charging power (user limit)
- Set DPM limit (Dynamic Power Management)
- Dynamic data refresh based on the wallbox state
- Command queue system to avoid Bluetooth congestion

### Sensors & Telemetry

- Wallbox state (ready, charging, paused, connected etc)
- Instant power (kW)
- Instant DPM power
- Voltage
- Charging session duration (in minutes)
- Energy delivered in the current session (kWh, auto‑reset at each new session)
- Raw data output from the wallbox (for debugging/advanced use)

### Manual Command Service (Advanced Users)

A dedicated ESPHome service allows sending manual commands to the wallbox.

The commands that can be sent are the following and the raw output returned by the wallbox is exposed through a text sensor named Raw: 

### EEPROM / Data Commands

- READ ALARMS → $EEP,READ,AL,{alarmnum}
- READ MANUFACTURING → $EEP,READ,MF
- READ CHARGING SESSIONS → $EEP,READ,SL,{sessionnum}
- READ SETTINGS → $EEP,READ,ST
- READ APP DATA → $DATA,READ,AD
- READ HW SETTINGS → $DATA,READ,HS
- READ SUPPLY VOLTAGE → $DATA,READ,SV

### Write Commands

- SET USER LIMIT → $EEP,WRITE,IDX,174,{limit}
- SET DPM LIMIT → $EEP,WRITE,IDX,158,{limit}
- SET DPM OFF → $EEP,WRITE,IDX,178,0
- SET DPM ON → $EEP,WRITE,IDX,178,1

### Read Commands

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


