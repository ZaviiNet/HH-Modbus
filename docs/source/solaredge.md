# SolarEdge Setup Guide

> **Credit:** [binsentsu/home-assistant-solaredge-modbus](https://github.com/binsentsu/home-assistant-solaredge-modbus)  
> Register map based on the SunSpec Alliance Modbus Interface specification as implemented by SolarEdge.

---

## Supported Models

| Model | Phases | Battery |
|---|---|---|
| SolarEdge-Single-Phase | 1 | No |
| SolarEdge-Three-Phase | 3 | No |
| SolarEdge-StorEdge | 1 | Yes (StorEdge battery) |
| SolarEdge-StorEdge-3P | 3 | Yes (StorEdge battery) |

If your model is not listed, open an [issue](https://github.com/ZaviiNet/HH-Modbus/issues) with your model.

---

## Connection Requirements

SolarEdge inverters use **Modbus TCP on port 1502** (not the standard 502). The default Modbus slave address is **1**.

### Enabling Modbus on SolarEdge

Modbus TCP must be enabled in the inverter's on-device display:

1. Access the inverter front panel → `Communication` → `LAN` → `Modbus TCP`.
2. Set **Modbus TCP** to **Enabled**.
3. Note the inverter's IP address shown in `Communication → LAN`.

> If the inverter is behind a SolarEdge gateway or hub, the gateway's IP is used instead.

---

## Configuration in HH Modbus Control

1. Add the integration and select **SolarEdge** as the brand.
2. Select **TCP** as the connection method.
3. Enter:
   - **Host** — Your inverter's local IP address.
   - **Port** — `1502` (pre-filled).
   - **Slave ID** — Default `1`.
   - **Inverter Serial** — Found on the inverter label.
   - **Model** — Select from the dropdown.
4. Click **Submit** — the integration will attempt a test connection.

---

## Register Map Overview

SolarEdge inverters follow the **SunSpec** standard. All registers are **holding registers** (function code 3) at the 40000+ address block.

### Common Block — Device Info (40004–40060)

Read once at startup.

| Address | Sensor | Notes |
|---|---|---|
| 40004–40019 | Manufacturer | 16-register ASCII string |
| 40020–40035 | Model | 16-register ASCII string |
| 40036–40043 | Firmware Version | 8-register ASCII string |
| 40044–40059 | Serial Number | 16-register ASCII string |
| 40060 | Device Address | Modbus slave ID |

### Inverter Model Block — Live Data (40071–40108)

Polled on every cycle.

| Address | Sensor | Scale | Unit | Notes |
|---|---|---|---|---|
| 40071 | AC Total Current | ÷10 | A | SF at 40075 (typical −1) |
| 40072 | Phase A Current | ÷10 | A | — |
| 40073 | Phase B Current | ÷10 | A | 3-phase only |
| 40074 | Phase C Current | ÷10 | A | 3-phase only |
| 40075 | AC Current Scale Factor | — | — | Internal; hidden |
| 40076 | Voltage A–B | ÷10 | V | — |
| 40077 | Voltage B–C | ÷10 | V | 3-phase only |
| 40078 | Voltage C–A | ÷10 | V | 3-phase only |
| 40079 | Phase A Voltage | ÷10 | V | Line-to-neutral |
| 40080 | Phase B Voltage | ÷10 | V | 3-phase only |
| 40081 | Phase C Voltage | ÷10 | V | 3-phase only |
| 40083 | AC Power | ×1 | W | Signed int16 |
| 40085 | AC Frequency | ÷100 | Hz | — |
| 40087 | Apparent Power | ×1 | VA | Signed int16 |
| 40089 | Reactive Power | ×1 | var | Signed int16 |
| 40091 | Power Factor | ÷100 | % | Signed int16 |
| 40093–40094 | AC Energy Total | ÷1000 | kWh | U32; lifetime generation |
| 40096 | DC Current | ÷100 | A | PV string current |
| 40098 | DC Voltage | ÷10 | V | PV string voltage |
| 40100 | DC Power | ×1 | W | Signed int16 |
| 40103 | Heatsink Temperature | ÷100 | °C | Signed int16 |
| 40107 | Inverter Status | — | — | 1=Off, 2=Sleeping, 3=Starting, 4=Producing, 5=Throttled, 6=Shutting Down, 7=Fault, 8=Standby |

---

## Scale Factors

SunSpec pairs each measurement register with a **scale factor register** (SF). The SF is a signed 16-bit integer — typically −1, −2, or −3 — that indicates the power of 10 multiplier.

This integration uses **fixed multipliers** matching the typical SolarEdge production SF values:

| Register | Typical SF | Fixed multiplier used |
|---|---|---|
| AC Current (40071) | −1 | 0.1 |
| AC Voltage (40079) | −1 | 0.1 |
| AC Power (40083) | 0 | 1 |
| AC Frequency (40085) | −2 | 0.01 |
| AC Energy (40093) | −3 | 0.001 |
| DC Current (40096) | −2 | 0.01 |
| DC Voltage (40098) | −1 | 0.1 |

> **If readings appear off by a power of 10**, check the SF register for that value (shown in HA as a hidden sensor) and open an issue. SolarEdge sometimes uses non-typical scale factors on certain firmware versions.

---

## Sensor Categories

| Category | Example sensors |
|---|---|
| `BASIC_INFORMATION` | Manufacturer, model, firmware, serial number |
| `AC_INFORMATION` | Phase voltages, currents, power, frequency |
| `PV_INFORMATION` | DC voltage, DC current, DC power |
| `ENERGY_DATA` | AC Energy Total (lifetime generation) |
| `STATUS_INFORMATION` | Inverter status, heatsink temperature |

---

## Known Limitations

- **Scale factors:** Fixed multipliers are used. Very old or very new firmware may use different SFs.
- **StorEdge battery:** The StorEdge battery registers (SunSpec block at ~0xE000 / 57344+) are not yet implemented.
- **Meter registers:** The SolarEdge Revenue Meter registers (SunSpec block at ~40121+) are not yet implemented.
- **Write support:** Control registers (power export limit, reactive power control) are not yet exposed. Planned for a future release.
