# Skyline / Duracell G3 Setup Guide

> **Credit:** [iPeel/HA-Skyline](https://github.com/iPeel/HA-Skyline)  
> Register map sourced from `custom_components/cyg_skyline/controller.py` and `inverter.py`.

The **Duracell G3** is a rebrand of the Skyline inverter. Both models share the same Modbus register map, with one difference: the DCDC software version register (`0x1A1C`) is unpopulated on Duracell G3 units and must not be polled.

---

## Supported Models

### Skyline

| Model | Phases |
|---|---|
| Skyline-3K | 1 |
| Skyline-5K | 1 |
| Skyline-6K | 3 |
| Skyline-10K | 3 |

### Duracell G3

| Model | Phases |
|---|---|
| Duracell-G3-3K | 1 |
| Duracell-G3-5K | 1 |
| Duracell-G3-6K | 3 |
| Duracell-G3-10K | 3 |

---

## Wiring

Skyline and Duracell G3 inverters expose an **RS485 port** for monitoring/meter communication. The terminal block pinout (typically a 10-pin connector) is:

| Pin | Function |
|---|---|
| 1 | RS485_A1 (for Meter) |
| 3 | RS485_B1 (for Meter) |
| 5 | NC |
| 7 | RS485_A2 (for Common Use) |
| 9 | RS485_B2 (for Common Use) |
| 2 | NC |
| 4 | I_CT- (for CT) |
| 6 | I_CT+ (for CT) |
| 8 | +3.3V (for CT) |
| 10 | CT_DET (for CT) |

Connect **pins 7 (A) and 9 (B)** to your RS485 adapter or Modbus-TCP gateway.

You can connect via either:

- A **USB↔RS485 adapter** (e.g. [Waveshare USB to RS485](waveshare-usb-rs485.md)) plugged directly into the Home Assistant host — choose **Serial** as the connection type.
- A **Modbus-TCP gateway** (e.g. Waveshare RS485-to-TCP) on the same LAN — choose **TCP** as the connection type.

---

## Configuration in HH Modbus Control

1. Add the integration and select **Skyline** or **Duracell G3** as the brand.
2. Select your connection type (TCP or Serial).
3. Enter:
   - **Host** — Your inverter's IP (or gateway IP).
   - **Port** — `502` (default).
   - **Slave ID** — Default `1`.
   - **Inverter Serial** — Found on the inverter label.
   - **Model** — Select from the dropdown.
4. Click **Submit** — the integration will attempt a test connection.

---

## Register Map Overview

All registers are **holding registers** (function code 3).

### Identity Blocks

| Block start | Address (hex) | Registers | Contents |
|---|---|---|---|
| 6656 | 0x1A00 | 8 | Model Number (ASCII string) |
| 6672 | 0x1A10 | 8 | Serial Number (ASCII string) |

### Software Version Blocks

| Block start | Address (hex) | Registers | Contents |
|---|---|---|---|
| 6694 | 0x1A26 | 3 | Master Software Version |
| 6697 | 0x1A29 | 3 | Slave Software Version |
| 6752 | 0x1A60 | 3 | EMS Software Version |
| 6684 | 0x1A1C | 3 | DCDC Software Version (**Skyline only** — absent on Duracell G3) |

### Inverter Power Data — Block 0x1001 (4097)

64 holding registers covering PV strings, phase loads, temperature, and daily energy.

| Register | Hex | Contents | Scale | Unit |
|---|---|---|---|---|
| 4099–4100 | 0x1003–0x1004 | Phase A Inverter Load | ÷10000 | kW (S32) |
| 4104–4105 | 0x1008–0x1009 | Phase B Inverter Load | ÷10000 | kW (S32) |
| 4109–4110 | 0x100D–0x100E | Phase C Inverter Load | ÷10000 | kW (S32) |
| 4112 | 0x1010 | MPPT1 Voltage | ÷10 | V |
| 4113 | 0x1011 | MPPT1 Current | ÷100 | A |
| 4114–4115 | 0x1012–0x1013 | MPPT1 Power | ÷10000 | kW (U32) |
| 4116 | 0x1014 | MPPT2 Voltage | ÷10 | V |
| 4117 | 0x1015 | MPPT2 Current | ÷100 | A |
| 4118–4119 | 0x1016–0x1017 | MPPT2 Power | ÷10000 | kW (U32) |
| 4124 | 0x101C | System Temperature | ×1 | °C (S16) |
| 4129–4130 | 0x1021–0x1022 | PV Energy Total | ×1 | kWh (U32) |
| 4135–4136 | 0x1027–0x1028 | PV Energy Today | ÷1000 | kWh (U32) |

### Grid Data — Block 0x1300 (4864)

63 holding registers covering grid power flow and energy totals.

| Register | Hex | Contents | Scale | Unit |
|---|---|---|---|---|
| 4864–4865 | 0x1300–0x1301 | Grid Load | ÷10000 | kW (S32) |
| 4870–4871 | 0x1306–0x1307 | Grid Energy In Total | ÷100 | kWh (U32) |
| 4872–4873 | 0x1308–0x1309 | Grid Energy Out Total | ÷100 | kWh (U32) |
| 4874–4875 | 0x130A–0x130B | Grid Tied Load | ÷10000 | kW (S32) |
| 4890 | 0x131A | Grid Voltage | ÷10 | V |
| 4893–4894 | 0x131D–0x131E | Grid Current | ÷100 | A (S32) |
| 4914–4915 | 0x1332–0x1333 | Grid Energy In Today | ÷100 | kWh (U32) |
| 4916–4917 | 0x1334–0x1335 | Grid Energy Out Today | ÷100 | kWh (U32) |

### Battery Data — Block 0x2000 (8192)

19 holding registers.

| Register | Hex | Contents | Scale | Unit |
|---|---|---|---|---|
| 8192 | 0x2000 | Battery SOC | ×1 | % |
| 8198 | 0x2006 | Battery Voltage | ÷10 | V |
| 8199–8200 | 0x2007–0x2008 | Battery Current | ÷100 | A (S32) |
| 8201–8202 | 0x2009–0x200A | Battery Power | ÷10000 | kW (S32) |
| 8203–8204 | 0x200B–0x200C | Battery Charge Today | ÷100 | kWh (U32) |
| 8205–8206 | 0x200D–0x200E | Battery Charge Total | ÷100 | kWh (U32) |
| 8207–8208 | 0x200F–0x2010 | Battery Discharge Today | ÷100 | kWh (U32) |
| 8209–8210 | 0x2011–0x2012 | Battery Discharge Total | ÷100 | kWh (U32) |

---

## Duracell G3 — Differences from Skyline

The Duracell G3 is code-identical to Skyline with one difference:

- **DCDC Software Version register (0x1A1C / 6684)** — this register is present on Skyline inverters but **absent** on Duracell G3 units. Polling it on a Duracell G3 may cause a Modbus exception error.

When you select **Duracell G3** in the HH Modbus Control setup wizard, this register is automatically excluded from polling.

---

## Sensor Categories

| Category | Example sensors |
|---|---|
| `BASIC_INFORMATION` | Model number, serial number, software versions |
| `PV_INFORMATION` | MPPT1/2 voltage, current, power; PV energy today/total |
| `AC_INFORMATION` | Phase A/B/C inverter load |
| `GRID_CODE_INFORMATION` | Grid load, grid tied load, grid voltage, grid current |
| `ENERGY_DATA` | Grid import/export today & total |
| `BATTERY_INFORMATION` | SOC, voltage, current, power, charge/discharge energy |
| `STATUS_INFORMATION` | System temperature |

---

## Known Limitations

- **3-phase load sum:** The individual phase loads (Phase A, B, C) are exposed. Total inverter load is their sum; a Home Assistant template sensor combining the three is recommended.
- **Configuration registers (0x2100):** Hybrid work mode, charge/discharge power limits, and EPS settings are not yet exposed as writable entities. Planned for a future release.
- **EPS block (0x1350):** EPS/backup power registers are not yet implemented.
