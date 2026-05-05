# Sun-Synk / Deye Setup Guide

This page covers Sun-Synk and Deye single-phase hybrid inverter support in HH Modbus Control.

> **Status:** Input (read-only) sensors and editable holding-register `number` entities are fully supported.  
> `switch`, `time`, and `select` scheduling entities are planned — see the [Roadmap](../../README.md#roadmap).

---

## Supported Models

| Model | Wattage | Phases |
|---|---|---|
| SUN-5K-SG01LP1 | 5 kW | 1 |
| SUN-8K-SG01LP1 | 8 kW | 1 |
| SUN-5K-SG01LP1-AU | 5 kW | 1 |
| SUN-6K-OG01LP1 | 6 kW | 1 |
| DEYE-5K-SG01LP1 | 5 kW | 1 |
| DEYE-8K-SG01LP1 | 8 kW | 1 |

If your model is not listed, open an [issue](https://github.com/ZaviiNet/HH-Modbus/issues) with your model number and we'll add it.

---

## Wiring

Sun-Synk / Deye inverters expose an **RS485 port** (typically on the bottom or back panel, labelled "485" or "COM"). Connect this to:

- a **USB-RS485 adapter** plugged into the Home Assistant host, **or**
- a **Modbus-TCP gateway** (e.g. Waveshare RS485-to-TCP, USR-W610) on your LAN.

Default RS485 settings:

| Parameter | Value |
|---|---|
| Baud rate | 9600 |
| Data bits | 8 |
| Parity | None |
| Stop bits | 1 |
| Slave ID | 1 |

---

## Configuration in HH Modbus Control

1. Add the integration and select **Sun-Synk / Deye** as the brand.
2. Select your connection type (TCP or Serial).
3. Enter:
   - Your **Inverter Serial Number** (found on the inverter label).
   - The **Modbus Slave ID** (default `1`).
   - Your model from the dropdown.
4. Click **Submit** — the integration will attempt a test connection.

---

## Register Map Overview

All Sun-Synk registers are split into two types:

### Input Registers (read-only, `0x04`)

Polled continuously for real-time measurements.

| Register range | Contents |
|---|---|
| 0–15 | Device info, fault codes |
| 16–62 | Grid, battery, PV measurements |
| 63–108 | Energy totals and counters |
| 109–149 | Extended battery & PV data |
| 150–196 | AC voltage, current, power |
| 197–250 | Additional measurements |

### Holding Registers (read/write, `0x03` / `0x06`)

Used for configuration and control. Entities created on the `number` platform.

| Register | Name | Notes |
|---|---|---|
| 16–17 | Rated Power | 32-bit pair, read-only via number |
| 43 | Inverter Enabled | 0 = off, 1 = on |
| 53 | Max Solar Power | Watts |
| 200 | Control Mode | |
| 201 | Battery Equalization Voltage | V × 0.01 |
| 202 | Battery Absorption Voltage | V × 0.01 |
| 203 | Battery Float Voltage | V × 0.01 |
| 204–206 | Battery voltage thresholds | |
| 210 | Battery Type | 0 = Lead, 1 = Lithium |
| 211 | Battery Capacity | Ah |

> For the complete register list, refer to the Sun-Synk RS485 Modbus protocol document for your firmware version.

---

## Sensor Categories

Sensors are grouped by `category` in the integration:

| Category | Example sensors |
|---|---|
| `BASIC_INFORMATION` | Device type, rated power |
| `BATTERY_INFORMATION` | Battery voltage, current, SOC, temperature |
| `PV_INFORMATION` | PV1/PV2 voltage, current, power |
| `AC_INFORMATION` | Grid voltage, current, frequency, power |
| `ENERGY_DATA` | Daily / total PV, load, grid import/export energy |
| `STATUS_INFORMATION` | Inverter temperature, fan speed, SD status |
| `POWER_FLOW` | Battery, grid, load, PV power (real-time) |
| `BASIC_SETTING` | Editable control registers |
| `BATTERY_SETTING` | Editable battery voltage / current limits |
| `POWER_CONTROL_SETTING` | Editable power limits |

---

## Known Limitations

- **3-phase models** are not yet validated. If you have a 3-phase Sun-Synk/Deye, please test and report.
- **Time-slot scheduling** (`switch`, `time`, `select` entities) is not yet implemented for Sun-Synk. The Modbus register addresses for scheduling differ from Solis, and implementation is planned in an upcoming release.
- The integration uses the **same `number` platform** for editable registers. Sensors marked `editable: true` in the holding register definitions will appear as number entities.

---

## Troubleshooting

### "Cannot connect" during setup

- Confirm Slave ID is `1` (check inverter display menu or documentation).
- Ensure no other device is polling the RS485 bus at the same time.
- Try reducing baud rate to `4800` if `9600` fails on some USB adapters.

### Sensors reading 0 or garbage values

- Verify the multiplier is correct for your firmware. Some older Sun-Synk firmware versions use different scale factors.
- Check HA logs for `hh_modbus_control` warnings about specific registers.

### Missing sensors

Some registers may not be populated on all models. The integration skips `reserve` placeholder registers automatically; if a sensor you expect is missing, check the register list and open an issue.
