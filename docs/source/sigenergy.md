# Sigenergy Setup Guide

> **Credit:** [TypQxQ/Sigenergy-Local-Modbus](https://github.com/TypQxQ/Sigenergy-Local-Modbus)  
> Register map sourced from `custom_components/sigen/modbusregisterdefinitions.py`.

---

## Supported Models

| Model | Phases |
|---|---|
| Sigenergy-5K | 1 |
| Sigenergy-8K | 1 |
| Sigenergy-10K | 3 |
| Sigenergy-15K | 3 |
| Sigenergy-20K | 3 |

If your model is not listed, open an [issue](https://github.com/ZaviiNet/HH-Modbus/issues) with your model number.

---

## Connection Requirements

Sigenergy ESS communicates over **local Modbus TCP** (standard port **502**).

The integration reads **plant-level** registers starting at address **30000**. These aggregate data across all connected inverters and batteries in the ESS.

### Finding your inverter's IP address

Check your router's DHCP leases or the Sigenergy app for the inverter's local IP.

---

## Configuration in HH Modbus Control

1. Add the integration and select **Sigenergy** as the brand.
2. Select **TCP** as the connection method.
3. Enter:
   - **Host** — Your inverter's local IP address.
   - **Port** — `502` (default).
   - **Slave ID** — Default `1`.
   - **Inverter Serial** — Found on the inverter label.
   - **Model** — Select from the dropdown.
4. Click **Submit** — the integration will attempt a test connection.

---

## Register Map Overview

All registers use Modbus **holding registers** (function code 3). Despite being "read-only" operational data, Sigenergy places them in the holding register space.

### Plant-Level Running Info (30000–30051)

| Address | Sensor | Scale | Unit | Notes |
|---|---|---|---|---|
| 30003 | EMS Work Mode | — | — | 0=MaxSelfConsumption, 1=AI, 2=TOU, 5=FullFeedIn, 7=Remote |
| 30004 | Grid Sensor Status | — | — | 0=disconnected, 1=connected |
| 30005–30006 | Grid Active Power | ÷1000 | kW | S32; >0 buy, <0 sell |
| 30009 | On/Off Grid Status | — | — | 0=ongrid, 1=offgrid auto, 2=offgrid manual |
| 30014 | Battery SOC | ÷10 | % | Plant-level aggregate |
| 30015–30016 | Phase A Active Power | ÷1000 | kW | S32 |
| 30017–30018 | Phase B Active Power | ÷1000 | kW | S32 |
| 30019–30020 | Phase C Active Power | ÷1000 | kW | S32 |
| 30031–30032 | Plant Active Power | ÷1000 | kW | S32 |
| 30035–30036 | PV Power | ÷1000 | kW | S32 |
| 30037–30038 | Battery Power | ÷1000 | kW | S32; <0=discharge, >0=charge |
| 30047–30048 | Max Charging Power | ÷1000 | kW | — |
| 30049–30050 | Max Discharging Power | ÷1000 | kW | — |
| 30051 | Plant Running State | — | — | 0=Standby, 1=Running, 2=Fault, 3=Shutdown |

### Energy Totals (30064–30093)

| Address | Sensor | Scale | Unit |
|---|---|---|---|
| 30083–30084 | Battery Rated Energy Capacity | ÷100 | kWh |
| 30085 | Battery Charge Cut-off SOC | ÷10 | % |
| 30086 | Battery Discharge Cut-off SOC | ÷10 | % |
| 30087 | Battery State of Health | ÷10 | % |
| 30088–30089 | Total PV Energy | ÷100 | kWh |
| 30092–30093 | Today Consumed Energy | ÷100 | kWh |

### Accumulated Battery & Grid Energy (30200–30223)

| Address | Sensor | Scale | Unit |
|---|---|---|---|
| 30200–30201 | Total Battery Charge Energy | ÷100 | kWh |
| 30204–30205 | Total Battery Discharge Energy | ÷100 | kWh |
| 30216–30217 | Total Grid Import Energy | ÷100 | kWh |
| 30220–30221 | Total Grid Export Energy | ÷100 | kWh |

---

## Sensor Categories

| Category | Example sensors |
|---|---|
| `BASIC_INFORMATION` | System time, timezone |
| `BATTERY_INFORMATION` | SOC, SOH, battery power, charge/discharge energy, capacity |
| `PV_INFORMATION` | PV power, total PV energy |
| `AC_INFORMATION` | Phase A/B/C active and reactive power |
| `GRID_CODE_INFORMATION` | Grid active power, grid sensor status |
| `STATUS_INFORMATION` | EMS work mode, on/off-grid status, running state |
| `ENERGY_DATA` | Grid import/export totals, consumed energy |

---

## Known Limitations

- **Plant-level only:** The current implementation reads plant-level aggregate registers (30000–30223). Per-inverter registers (~32000) and per-battery registers (~35000) are planned for a future release.
- **Write support:** Writable holding registers for EMS configuration are not yet exposed as `number` / `select` entities. This is planned.
- **U64 registers:** Several energy accumulation registers are 64-bit (4 × 16-bit). The integration currently reads only the low 32-bit word. For systems with very high cumulative energy (>42,949,672 kWh), the value will overflow. This affects virtually no real-world deployment.
