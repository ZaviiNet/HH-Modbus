# GivEnergy Setup Guide

> **Credit:** [cdpuk/givenergy-local](https://github.com/cdpuk/givenergy-local)  
> Register map sourced from `givenergy_modbus/model/inverter.py` and `battery.py`.

---

## Supported Models

| Model | Phases | Connection Port |
|---|---|---|
| GivEnergy-Hybrid-1P | 1 | 8899 |
| GivEnergy-Hybrid-3P | 3 | 8899 |
| GivEnergy-AC-Coupled | 1 | 8899 |

If your model is not listed, open an [issue](https://github.com/ZaviiNet/HH-Modbus/issues) with your model number.

---

## Connection Requirements

GivEnergy inverters use **Modbus TCP on port 8899** (not the standard port 502).

> **Generation note:**
> - **Gen 3 inverters** support standard Modbus TCP framing on port 8899 and are fully compatible with this integration.
> - **Gen 1 / Gen 2 inverters** use a proprietary TCP framing layer. These may work with this integration but are not guaranteed — if you experience issues, try the upstream [givenergy-local](https://github.com/cdpuk/givenergy-local) integration instead.

### Finding your inverter's IP address

1. Open the GivEnergy app → *Settings → WiFi* to find the IP.
2. Alternatively, check your router's DHCP leases for a device named `GivEnergy` or with a GivEnergy MAC prefix.

---

## Configuration in HH Modbus Control

1. Add the integration and select **GivEnergy** as the brand.
2. Select **TCP** as the connection method.
3. Enter:
   - **Host** — Your inverter's local IP address.
   - **Port** — `8899` (pre-filled).
   - **Slave ID** — Default `1`.
   - **Inverter Serial** — Found on the inverter label.
   - **Model** — Select from the dropdown.
4. Click **Submit** — the integration will attempt a test connection.

---

## Register Map Overview

### Input Registers (IR) — Real-Time Data

Polled continuously. All addresses are 0-based (Modbus function code 4).

| IR | Sensor | Unit | Notes |
|---|---|---|---|
| 0 | Inverter Status | — | 0=Waiting, 1=Normal, 2=Warning, 3=Fault |
| 1 | PV1 Voltage | V | ÷10 |
| 2 | PV2 Voltage | V | ÷10 |
| 5 | AC Voltage | V | ÷10 |
| 6–7 | Battery Throughput Total | kWh | U32 ÷10 |
| 8 | PV1 Current | A | ÷100 |
| 9 | PV2 Current | A | ÷100 |
| 10 | AC Current | A | ÷100 |
| 11–12 | PV Total Energy | kWh | U32 ÷10 |
| 13 | AC Frequency | Hz | ÷100 |
| 17 | PV1 Today Energy | kWh | ÷10 |
| 18 | PV1 Power | W | — |
| 19 | PV2 Today Energy | kWh | ÷10 |
| 20 | PV2 Power | W | — |
| 21–22 | Grid Export Total | kWh | U32 ÷10 |
| 24 | AC Output Power | W | signed int16 |
| 25 | Grid Export Today | kWh | ÷10 |
| 26 | Grid Import Today | kWh | ÷10 |
| 27–28 | Inverter In Total | kWh | U32 ÷10 |
| 30 | Grid Power | W | signed int16; negative = export |
| 31 | EPS Backup Power | W | — |
| 32–33 | Grid Import Total | kWh | U32 ÷10 |
| 36 | Battery Charge Today | kWh | ÷10 |
| 37 | Battery Discharge Today | kWh | ÷10 |
| 41 | Heatsink Temperature | °C | ÷10 |
| 42 | Load Demand | W | — |
| 44 | Inverter Out Today | kWh | ÷10 |
| 45–46 | Inverter Out Total | kWh | U32 ÷10 |
| 49 | System Mode | — | — |
| 50 | Battery Voltage | V | ÷100 |
| 51 | Battery Current | A | signed int16 ÷100 |
| 52 | Battery Power | W | signed int16 |
| 55 | Charger Temperature | °C | ÷10 |
| 56 | Battery Temperature | °C | ÷10 |
| 58 | Grid Port Current | A | ÷100 |
| 59 | Battery SOC | % | — |

### Holding Registers (HR) — Device Info

Read once at startup (function code 3).

| HR | Sensor | Notes |
|---|---|---|
| 0 | Device Type Code | Model identifier |
| 8–12 | Battery Serial Number | 5-register ASCII string |
| 13–17 | Inverter Serial Number | 5-register ASCII string |
| 18 | Battery BMS Firmware Version | — |
| 19 | DSP Firmware Version | — |
| 21 | ARM Firmware Version | Gen 1=1xx, Gen 2=2xx, Gen 3=3xx |

---

## Sensor Categories

| Category | Example sensors |
|---|---|
| `BASIC_INFORMATION` | Serial number, firmware versions |
| `PV_INFORMATION` | PV1/PV2 voltage, current, power, daily energy |
| `BATTERY_INFORMATION` | Battery voltage, current, power, SOC, temperature, throughput |
| `AC_INFORMATION` | AC voltage, current, frequency, EPS backup |
| `GRID_CODE_INFORMATION` | Grid power, port current |
| `LOAD_INFORMATION` | Load demand |
| `ENERGY_DATA` | Daily/total energy import, export, generation |
| `STATUS_INFORMATION` | Inverter status, heatsink temperature, system mode |

---

## Known Limitations

- **Gen 1/2 framing:** Only Gen 3 inverters are confirmed compatible with this integration. Gen 1/2 uses a proprietary framing wrapper around Modbus.
- **Battery slave addresses:** GivEnergy supports multiple battery packs on separate Modbus slave addresses. Currently only the primary inverter registers are polled. Per-battery registers are planned.
- **Writable registers:** Control registers (charge/discharge slots, SOC targets) are read in the sensor data but write support (`number` entities) is planned for a future release.
