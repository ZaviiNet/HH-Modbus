"""Skyline / Duracell G3 hybrid inverter sensor definitions.

Credit: iPeel/HA-Skyline (https://github.com/iPeel/HA-Skyline)

Register map sourced from:
  iPeel/HA-Skyline:custom_components/cyg_skyline/controller.py
  iPeel/HA-Skyline:custom_components/cyg_skyline/inverter.py

Skyline and Duracell G3 inverters use local Modbus TCP.
The Duracell G3 is a rebranded Skyline inverter with an identical register map,
except the DCDC software version register (0x1A1C) is unpopulated.

Register block addresses (all holding registers):
  0x1001 (4097)  — Inverter power / PV data
  0x1300 (4864)  — Grid data
  0x1350 (4944)  — EPS / backup data
  0x1A00 (6656)  — Model number string
  0x1A10 (6672)  — Serial number string
  0x1A26 (6694)  — Master software version
  0x1A60 (6752)  — EMS software version
  0x2000 (8192)  — Battery data
  0x2100 (8448)  — Inverter configuration

Decoding notes:
  Signed 32-bit values span two consecutive 16-bit registers (high word first).
  Power values are in units of ×10000 (÷10000 → kW).
  Voltage values are in units of ×10 (÷10 → V).
  Current values are in units of ×100 (÷100 → A).
  Energy values are in units of ×100 (÷100 → kWh).
"""

from homeassistant.components.sensor.const import SensorDeviceClass, SensorStateClass
from homeassistant.const import (
    PERCENTAGE,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
)

from custom_components.hh_modbus_control.data.enums import Category, DataType, PollSpeed

# ---------------------------------------------------------------------------
# IDENTITY — Model Number & Serial Number (read once at startup)
# Block 0x1A00 (6656): model_number — 8 holding registers
# Block 0x1A10 (6672): serial_number — 8 holding registers
# ---------------------------------------------------------------------------

skyline_identity_sensors = [
    {
        "register_start": 6656,   # 0x1A00
        "poll_speed": PollSpeed.ONCE,
        "register_type": "holding",
        "entities": [
            {
                "name": "Model Number",
                "unique": "skyline_model_number",
                "category": Category.BASIC_INFORMATION,
                "register": [str(r) for r in range(6656, 6664)],
                "multiplier": 0,
            },
        ],
    },
    {
        "register_start": 6672,   # 0x1A10
        "poll_speed": PollSpeed.ONCE,
        "register_type": "holding",
        "entities": [
            {
                "name": "Serial Number",
                "unique": "skyline_serial_number",
                "category": Category.BASIC_INFORMATION,
                "register": [str(r) for r in range(6672, 6680)],
                "multiplier": 0,
            },
        ],
    },
]

# ---------------------------------------------------------------------------
# SOFTWARE VERSIONS — read once at startup
# 0x1A26 (6694): Master software version — 3 registers
# 0x1A60 (6752): EMS software version — 3 registers
# ---------------------------------------------------------------------------

skyline_version_sensors = [
    {
        "register_start": 6694,   # 0x1A26
        "poll_speed": PollSpeed.ONCE,
        "register_type": "holding",
        "entities": [
            {
                "name": "Master Software Version",
                "unique": "skyline_master_software_version",
                "category": Category.BASIC_INFORMATION,
                "register": ["6694", "6695", "6696"],
                "multiplier": 0,
            },
            # 0x1A29 (6697) — Slave software version (3 regs)
            {
                "name": "Slave Software Version",
                "unique": "skyline_slave_software_version",
                "category": Category.BASIC_INFORMATION,
                "register": ["6697", "6698", "6699"],
                "multiplier": 0,
            },
        ],
    },
    {
        "register_start": 6752,   # 0x1A60
        "poll_speed": PollSpeed.ONCE,
        "register_type": "holding",
        "entities": [
            {
                "name": "EMS Software Version",
                "unique": "skyline_ems_software_version",
                "category": Category.BASIC_INFORMATION,
                "register": ["6752", "6753", "6754"],
                "multiplier": 0,
            },
        ],
    },
]

# DCDC version — present on Skyline, absent on Duracell G3 (0x1A1C = 6684)
# Included conditionally in skyline_sensors / duracell_g3_sensors below.
skyline_dcdc_version_sensors = [
    {
        "register_start": 6684,   # 0x1A1C
        "poll_speed": PollSpeed.ONCE,
        "register_type": "holding",
        "entities": [
            {
                "name": "DCDC Software Version",
                "unique": "skyline_dcdc_software_version",
                "category": Category.BASIC_INFORMATION,
                "register": ["6684", "6685", "6686"],
                "multiplier": 0,
            },
        ],
    },
]

# ---------------------------------------------------------------------------
# INVERTER POWER DATA — Block 0x1001 (4097), 64 holding registers
# Covers PV strings, individual phase loads, system temperature, and energy totals.
# Phase load registers: offsets [2-3], [7-8], [12-13] — each is a signed 32-bit pair.
# ---------------------------------------------------------------------------

skyline_inverter_power_sensors = [
    {
        "register_start": 4097,   # 0x1001
        "poll_speed": PollSpeed.FAST,
        "register_type": "holding",
        "entities": [
            # Offset [0]: reserve
            {
                "name": "reserve_4097",
                "unique": "skyline_reserve_4097",
                "register": ["4097"],
                "multiplier": 0,
                "hidden": True,
            },
            # Offset [1]: reserve
            {
                "name": "reserve_4098",
                "unique": "skyline_reserve_4098",
                "register": ["4098"],
                "multiplier": 0,
                "hidden": True,
            },
            # Offset [2-3]: Phase A inverter load (signed int32 ÷10000 → kW)
            {
                "name": "Phase A Inverter Load",
                "unique": "skyline_phase_a_inverter_load",
                "category": Category.AC_INFORMATION,
                "register": ["4099", "4100"],
                "multiplier": 0.0001,
                "data_type": DataType.S32.value,
                "unit_of_measurement": UnitOfPower.KILO_WATT,
                "device_class": SensorDeviceClass.POWER,
                "state_class": SensorStateClass.MEASUREMENT,
            },
            # Offset [4]: reserve
            {
                "name": "reserve_4101",
                "unique": "skyline_reserve_4101",
                "register": ["4101"],
                "multiplier": 0,
                "hidden": True,
            },
            # Offset [5]: reserve
            {
                "name": "reserve_4102",
                "unique": "skyline_reserve_4102",
                "register": ["4102"],
                "multiplier": 0,
                "hidden": True,
            },
            # Offset [6]: reserve
            {
                "name": "reserve_4103",
                "unique": "skyline_reserve_4103",
                "register": ["4103"],
                "multiplier": 0,
                "hidden": True,
            },
            # Offset [7-8]: Phase B inverter load (signed int32 ÷10000 → kW)
            {
                "name": "Phase B Inverter Load",
                "unique": "skyline_phase_b_inverter_load",
                "category": Category.AC_INFORMATION,
                "register": ["4104", "4105"],
                "multiplier": 0.0001,
                "data_type": DataType.S32.value,
                "unit_of_measurement": UnitOfPower.KILO_WATT,
                "device_class": SensorDeviceClass.POWER,
                "state_class": SensorStateClass.MEASUREMENT,
            },
            # Offset [9-11]: reserve
            {
                "name": "reserve_4106",
                "unique": "skyline_reserve_4106",
                "register": ["4106"],
                "multiplier": 0,
                "hidden": True,
            },
            {
                "name": "reserve_4107",
                "unique": "skyline_reserve_4107",
                "register": ["4107"],
                "multiplier": 0,
                "hidden": True,
            },
            {
                "name": "reserve_4108",
                "unique": "skyline_reserve_4108",
                "register": ["4108"],
                "multiplier": 0,
                "hidden": True,
            },
            # Offset [12-13]: Phase C inverter load (signed int32 ÷10000 → kW)
            {
                "name": "Phase C Inverter Load",
                "unique": "skyline_phase_c_inverter_load",
                "category": Category.AC_INFORMATION,
                "register": ["4109", "4110"],
                "multiplier": 0.0001,
                "data_type": DataType.S32.value,
                "unit_of_measurement": UnitOfPower.KILO_WATT,
                "device_class": SensorDeviceClass.POWER,
                "state_class": SensorStateClass.MEASUREMENT,
            },
            # Offset [14]: reserve
            {
                "name": "reserve_4111",
                "unique": "skyline_reserve_4111",
                "register": ["4111"],
                "multiplier": 0,
                "hidden": True,
            },
            # Offset [15]: MPPT1 Voltage (÷10 → V)
            {
                "name": "MPPT1 Voltage",
                "unique": "skyline_mppt1_voltage",
                "category": Category.PV_INFORMATION,
                "register": ["4112"],
                "multiplier": 0.1,
                "unit_of_measurement": UnitOfElectricPotential.VOLT,
                "device_class": SensorDeviceClass.VOLTAGE,
                "state_class": SensorStateClass.MEASUREMENT,
            },
            # Offset [16]: MPPT1 Current (÷100 → A)
            {
                "name": "MPPT1 Current",
                "unique": "skyline_mppt1_current",
                "category": Category.PV_INFORMATION,
                "register": ["4113"],
                "multiplier": 0.01,
                "unit_of_measurement": UnitOfElectricCurrent.AMPERE,
                "device_class": SensorDeviceClass.CURRENT,
                "state_class": SensorStateClass.MEASUREMENT,
            },
            # Offset [17-18]: MPPT1 Power (U32 ÷10000 → kW)
            {
                "name": "MPPT1 Power",
                "unique": "skyline_mppt1_power",
                "category": Category.PV_INFORMATION,
                "register": ["4114", "4115"],
                "multiplier": 0.0001,
                "unit_of_measurement": UnitOfPower.KILO_WATT,
                "device_class": SensorDeviceClass.POWER,
                "state_class": SensorStateClass.MEASUREMENT,
            },
            # Offset [19]: MPPT2 Voltage (÷10 → V)
            {
                "name": "MPPT2 Voltage",
                "unique": "skyline_mppt2_voltage",
                "category": Category.PV_INFORMATION,
                "register": ["4116"],
                "multiplier": 0.1,
                "unit_of_measurement": UnitOfElectricPotential.VOLT,
                "device_class": SensorDeviceClass.VOLTAGE,
                "state_class": SensorStateClass.MEASUREMENT,
            },
            # Offset [20]: MPPT2 Current (÷100 → A)
            {
                "name": "MPPT2 Current",
                "unique": "skyline_mppt2_current",
                "category": Category.PV_INFORMATION,
                "register": ["4117"],
                "multiplier": 0.01,
                "unit_of_measurement": UnitOfElectricCurrent.AMPERE,
                "device_class": SensorDeviceClass.CURRENT,
                "state_class": SensorStateClass.MEASUREMENT,
            },
            # Offset [21-22]: MPPT2 Power (U32 ÷10000 → kW)
            {
                "name": "MPPT2 Power",
                "unique": "skyline_mppt2_power",
                "category": Category.PV_INFORMATION,
                "register": ["4118", "4119"],
                "multiplier": 0.0001,
                "unit_of_measurement": UnitOfPower.KILO_WATT,
                "device_class": SensorDeviceClass.POWER,
                "state_class": SensorStateClass.MEASUREMENT,
            },
            # Offsets [23-26]: reserve
            {
                "name": "reserve_4120",
                "unique": "skyline_reserve_4120",
                "register": ["4120"],
                "multiplier": 0,
                "hidden": True,
            },
            {
                "name": "reserve_4121",
                "unique": "skyline_reserve_4121",
                "register": ["4121"],
                "multiplier": 0,
                "hidden": True,
            },
            {
                "name": "reserve_4122",
                "unique": "skyline_reserve_4122",
                "register": ["4122"],
                "multiplier": 0,
                "hidden": True,
            },
            {
                "name": "reserve_4123",
                "unique": "skyline_reserve_4123",
                "register": ["4123"],
                "multiplier": 0,
                "hidden": True,
            },
            # Offset [27]: System Temperature (signed int16 → °C)
            {
                "name": "System Temperature",
                "unique": "skyline_system_temp",
                "category": Category.STATUS_INFORMATION,
                "register": ["4124"],
                "multiplier": 1,
                "data_type": DataType.S16.value,
                "unit_of_measurement": UnitOfTemperature.CELSIUS,
                "device_class": SensorDeviceClass.TEMPERATURE,
                "state_class": SensorStateClass.MEASUREMENT,
            },
            # Offsets [28-31]: reserve
            {
                "name": "reserve_4125",
                "unique": "skyline_reserve_4125",
                "register": ["4125"],
                "multiplier": 0,
                "hidden": True,
            },
            {
                "name": "reserve_4126",
                "unique": "skyline_reserve_4126",
                "register": ["4126"],
                "multiplier": 0,
                "hidden": True,
            },
            {
                "name": "reserve_4127",
                "unique": "skyline_reserve_4127",
                "register": ["4127"],
                "multiplier": 0,
                "hidden": True,
            },
            {
                "name": "reserve_4128",
                "unique": "skyline_reserve_4128",
                "register": ["4128"],
                "multiplier": 0,
                "hidden": True,
            },
            # Offset [32-33]: PV Energy Total (U32 raw → kWh)
            {
                "name": "PV Energy Total",
                "unique": "skyline_pv_energy_total",
                "category": Category.PV_INFORMATION,
                "register": ["4129", "4130"],
                "multiplier": 1,
                "unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR,
                "device_class": SensorDeviceClass.ENERGY,
                "state_class": SensorStateClass.TOTAL_INCREASING,
            },
            # Offsets [34-37]: reserve
            {
                "name": "reserve_4131",
                "unique": "skyline_reserve_4131",
                "register": ["4131"],
                "multiplier": 0,
                "hidden": True,
            },
            {
                "name": "reserve_4132",
                "unique": "skyline_reserve_4132",
                "register": ["4132"],
                "multiplier": 0,
                "hidden": True,
            },
            {
                "name": "reserve_4133",
                "unique": "skyline_reserve_4133",
                "register": ["4133"],
                "multiplier": 0,
                "hidden": True,
            },
            {
                "name": "reserve_4134",
                "unique": "skyline_reserve_4134",
                "register": ["4134"],
                "multiplier": 0,
                "hidden": True,
            },
            # Offset [38-39]: PV Energy Today (U32 ÷1000 → kWh)
            {
                "name": "PV Energy Today",
                "unique": "skyline_pv_energy_today",
                "category": Category.PV_INFORMATION,
                "register": ["4135", "4136"],
                "multiplier": 0.001,
                "unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR,
                "device_class": SensorDeviceClass.ENERGY,
                "state_class": SensorStateClass.TOTAL_INCREASING,
            },
        ],
    },
]

# ---------------------------------------------------------------------------
# GRID DATA — Block 0x1300 (4864), 63 holding registers
# ---------------------------------------------------------------------------

skyline_grid_sensors = [
    {
        "register_start": 4864,   # 0x1300
        "poll_speed": PollSpeed.FAST,
        "register_type": "holding",
        "entities": [
            # Offset [0-1]: Grid load (signed int32, avg 30 s, ÷10000 → kW; >0 import, <0 export)
            {
                "name": "Grid Load",
                "unique": "skyline_grid_load",
                "category": Category.GRID_CODE_INFORMATION,
                "register": ["4864", "4865"],
                "multiplier": 0.0001,
                "data_type": DataType.S32.value,
                "unit_of_measurement": UnitOfPower.KILO_WATT,
                "device_class": SensorDeviceClass.POWER,
                "state_class": SensorStateClass.MEASUREMENT,
            },
            # Offsets [2-5]: reserve
            {
                "name": "reserve_4866",
                "unique": "skyline_reserve_4866",
                "register": ["4866"],
                "multiplier": 0,
                "hidden": True,
            },
            {
                "name": "reserve_4867",
                "unique": "skyline_reserve_4867",
                "register": ["4867"],
                "multiplier": 0,
                "hidden": True,
            },
            {
                "name": "reserve_4868",
                "unique": "skyline_reserve_4868",
                "register": ["4868"],
                "multiplier": 0,
                "hidden": True,
            },
            {
                "name": "reserve_4869",
                "unique": "skyline_reserve_4869",
                "register": ["4869"],
                "multiplier": 0,
                "hidden": True,
            },
            # Offset [6-7]: Grid Energy In Total (U32 ÷100 → kWh)
            {
                "name": "Grid Energy In Total",
                "unique": "skyline_grid_energy_in_total",
                "category": Category.ENERGY_DATA,
                "register": ["4870", "4871"],
                "multiplier": 0.01,
                "unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR,
                "device_class": SensorDeviceClass.ENERGY,
                "state_class": SensorStateClass.TOTAL_INCREASING,
            },
            # Offset [8-9]: Grid Energy Out Total (U32 ÷100 → kWh)
            {
                "name": "Grid Energy Out Total",
                "unique": "skyline_grid_energy_out_total",
                "category": Category.ENERGY_DATA,
                "register": ["4872", "4873"],
                "multiplier": 0.01,
                "unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR,
                "device_class": SensorDeviceClass.ENERGY,
                "state_class": SensorStateClass.TOTAL_INCREASING,
            },
            # Offset [10-11]: Grid-tied load (signed int32, ÷10000 → kW)
            {
                "name": "Grid Tied Load",
                "unique": "skyline_grid_tied_load",
                "category": Category.LOAD_INFORMATION,
                "register": ["4874", "4875"],
                "multiplier": 0.0001,
                "data_type": DataType.S32.value,
                "unit_of_measurement": UnitOfPower.KILO_WATT,
                "device_class": SensorDeviceClass.POWER,
                "state_class": SensorStateClass.MEASUREMENT,
            },
            # Offsets [12-25]: reserve
            {
                "name": "reserve_4876",
                "unique": "skyline_reserve_4876",
                "register": ["4876"],
                "multiplier": 0,
                "hidden": True,
            },
            {
                "name": "reserve_4877",
                "unique": "skyline_reserve_4877",
                "register": ["4877"],
                "multiplier": 0,
                "hidden": True,
            },
            {
                "name": "reserve_4878",
                "unique": "skyline_reserve_4878",
                "register": ["4878"],
                "multiplier": 0,
                "hidden": True,
            },
            {
                "name": "reserve_4879",
                "unique": "skyline_reserve_4879",
                "register": ["4879"],
                "multiplier": 0,
                "hidden": True,
            },
            {
                "name": "reserve_4880",
                "unique": "skyline_reserve_4880",
                "register": ["4880"],
                "multiplier": 0,
                "hidden": True,
            },
            {
                "name": "reserve_4881",
                "unique": "skyline_reserve_4881",
                "register": ["4881"],
                "multiplier": 0,
                "hidden": True,
            },
            {
                "name": "reserve_4882",
                "unique": "skyline_reserve_4882",
                "register": ["4882"],
                "multiplier": 0,
                "hidden": True,
            },
            {
                "name": "reserve_4883",
                "unique": "skyline_reserve_4883",
                "register": ["4883"],
                "multiplier": 0,
                "hidden": True,
            },
            {
                "name": "reserve_4884",
                "unique": "skyline_reserve_4884",
                "register": ["4884"],
                "multiplier": 0,
                "hidden": True,
            },
            {
                "name": "reserve_4885",
                "unique": "skyline_reserve_4885",
                "register": ["4885"],
                "multiplier": 0,
                "hidden": True,
            },
            {
                "name": "reserve_4886",
                "unique": "skyline_reserve_4886",
                "register": ["4886"],
                "multiplier": 0,
                "hidden": True,
            },
            {
                "name": "reserve_4887",
                "unique": "skyline_reserve_4887",
                "register": ["4887"],
                "multiplier": 0,
                "hidden": True,
            },
            {
                "name": "reserve_4888",
                "unique": "skyline_reserve_4888",
                "register": ["4888"],
                "multiplier": 0,
                "hidden": True,
            },
            {
                "name": "reserve_4889",
                "unique": "skyline_reserve_4889",
                "register": ["4889"],
                "multiplier": 0,
                "hidden": True,
            },
            # Offset [26]: Grid Voltage (÷10 → V)
            {
                "name": "Grid Voltage",
                "unique": "skyline_grid_voltage",
                "category": Category.GRID_CODE_INFORMATION,
                "register": ["4890"],
                "multiplier": 0.1,
                "unit_of_measurement": UnitOfElectricPotential.VOLT,
                "device_class": SensorDeviceClass.VOLTAGE,
                "state_class": SensorStateClass.MEASUREMENT,
            },
            # Offsets [27-28]: reserve
            {
                "name": "reserve_4891",
                "unique": "skyline_reserve_4891",
                "register": ["4891"],
                "multiplier": 0,
                "hidden": True,
            },
            {
                "name": "reserve_4892",
                "unique": "skyline_reserve_4892",
                "register": ["4892"],
                "multiplier": 0,
                "hidden": True,
            },
            # Offset [29-30]: Grid Current (signed int32, ÷100 → A)
            {
                "name": "Grid Current",
                "unique": "skyline_grid_current",
                "category": Category.GRID_CODE_INFORMATION,
                "register": ["4893", "4894"],
                "multiplier": 0.01,
                "data_type": DataType.S32.value,
                "unit_of_measurement": UnitOfElectricCurrent.AMPERE,
                "device_class": SensorDeviceClass.CURRENT,
                "state_class": SensorStateClass.MEASUREMENT,
            },
            # Offsets [31-49]: reserve
            {
                "name": "reserve_4895",
                "unique": "skyline_reserve_4895",
                "register": ["4895"],
                "multiplier": 0,
                "hidden": True,
            },
            {
                "name": "reserve_4896",
                "unique": "skyline_reserve_4896",
                "register": ["4896"],
                "multiplier": 0,
                "hidden": True,
            },
            {
                "name": "reserve_4897",
                "unique": "skyline_reserve_4897",
                "register": ["4897"],
                "multiplier": 0,
                "hidden": True,
            },
            {
                "name": "reserve_4898",
                "unique": "skyline_reserve_4898",
                "register": ["4898"],
                "multiplier": 0,
                "hidden": True,
            },
            {
                "name": "reserve_4899",
                "unique": "skyline_reserve_4899",
                "register": ["4899"],
                "multiplier": 0,
                "hidden": True,
            },
            {
                "name": "reserve_4900",
                "unique": "skyline_reserve_4900",
                "register": ["4900"],
                "multiplier": 0,
                "hidden": True,
            },
            {
                "name": "reserve_4901",
                "unique": "skyline_reserve_4901",
                "register": ["4901"],
                "multiplier": 0,
                "hidden": True,
            },
            {
                "name": "reserve_4902",
                "unique": "skyline_reserve_4902",
                "register": ["4902"],
                "multiplier": 0,
                "hidden": True,
            },
            {
                "name": "reserve_4903",
                "unique": "skyline_reserve_4903",
                "register": ["4903"],
                "multiplier": 0,
                "hidden": True,
            },
            {
                "name": "reserve_4904",
                "unique": "skyline_reserve_4904",
                "register": ["4904"],
                "multiplier": 0,
                "hidden": True,
            },
            {
                "name": "reserve_4905",
                "unique": "skyline_reserve_4905",
                "register": ["4905"],
                "multiplier": 0,
                "hidden": True,
            },
            {
                "name": "reserve_4906",
                "unique": "skyline_reserve_4906",
                "register": ["4906"],
                "multiplier": 0,
                "hidden": True,
            },
            {
                "name": "reserve_4907",
                "unique": "skyline_reserve_4907",
                "register": ["4907"],
                "multiplier": 0,
                "hidden": True,
            },
            {
                "name": "reserve_4908",
                "unique": "skyline_reserve_4908",
                "register": ["4908"],
                "multiplier": 0,
                "hidden": True,
            },
            {
                "name": "reserve_4909",
                "unique": "skyline_reserve_4909",
                "register": ["4909"],
                "multiplier": 0,
                "hidden": True,
            },
            {
                "name": "reserve_4910",
                "unique": "skyline_reserve_4910",
                "register": ["4910"],
                "multiplier": 0,
                "hidden": True,
            },
            {
                "name": "reserve_4911",
                "unique": "skyline_reserve_4911",
                "register": ["4911"],
                "multiplier": 0,
                "hidden": True,
            },
            {
                "name": "reserve_4912",
                "unique": "skyline_reserve_4912",
                "register": ["4912"],
                "multiplier": 0,
                "hidden": True,
            },
            {
                "name": "reserve_4913",
                "unique": "skyline_reserve_4913",
                "register": ["4913"],
                "multiplier": 0,
                "hidden": True,
            },
            # Offset [50-51]: Grid Energy In Today (U32 ÷100 → kWh)
            {
                "name": "Grid Energy In Today",
                "unique": "skyline_grid_energy_in_today",
                "category": Category.ENERGY_DATA,
                "register": ["4914", "4915"],
                "multiplier": 0.01,
                "unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR,
                "device_class": SensorDeviceClass.ENERGY,
                "state_class": SensorStateClass.TOTAL_INCREASING,
            },
            # Offset [52-53]: Grid Energy Out Today (U32 ÷100 → kWh)
            {
                "name": "Grid Energy Out Today",
                "unique": "skyline_grid_energy_out_today",
                "category": Category.ENERGY_DATA,
                "register": ["4916", "4917"],
                "multiplier": 0.01,
                "unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR,
                "device_class": SensorDeviceClass.ENERGY,
                "state_class": SensorStateClass.TOTAL_INCREASING,
            },
        ],
    },
]

# ---------------------------------------------------------------------------
# BATTERY DATA — Block 0x2000 (8192), 19 holding registers
# ---------------------------------------------------------------------------

skyline_battery_sensors = [
    {
        "register_start": 8192,   # 0x2000
        "poll_speed": PollSpeed.FAST,
        "register_type": "holding",
        "entities": [
            # Offset [0]: Battery SOC (%)
            {
                "name": "Battery SOC",
                "unique": "skyline_battery_soc",
                "category": Category.BATTERY_INFORMATION,
                "register": ["8192"],
                "multiplier": 1,
                "unit_of_measurement": PERCENTAGE,
                "device_class": SensorDeviceClass.BATTERY,
                "state_class": SensorStateClass.MEASUREMENT,
            },
            # Offsets [1-5]: reserve
            {
                "name": "reserve_8193",
                "unique": "skyline_reserve_8193",
                "register": ["8193"],
                "multiplier": 0,
                "hidden": True,
            },
            {
                "name": "reserve_8194",
                "unique": "skyline_reserve_8194",
                "register": ["8194"],
                "multiplier": 0,
                "hidden": True,
            },
            {
                "name": "reserve_8195",
                "unique": "skyline_reserve_8195",
                "register": ["8195"],
                "multiplier": 0,
                "hidden": True,
            },
            {
                "name": "reserve_8196",
                "unique": "skyline_reserve_8196",
                "register": ["8196"],
                "multiplier": 0,
                "hidden": True,
            },
            {
                "name": "reserve_8197",
                "unique": "skyline_reserve_8197",
                "register": ["8197"],
                "multiplier": 0,
                "hidden": True,
            },
            # Offset [6]: Battery Voltage (÷10 → V)
            {
                "name": "Battery Voltage",
                "unique": "skyline_battery_voltage",
                "category": Category.BATTERY_INFORMATION,
                "register": ["8198"],
                "multiplier": 0.1,
                "unit_of_measurement": UnitOfElectricPotential.VOLT,
                "device_class": SensorDeviceClass.VOLTAGE,
                "state_class": SensorStateClass.MEASUREMENT,
            },
            # Offset [7-8]: Battery Current (signed int32 ÷100 → A)
            {
                "name": "Battery Current",
                "unique": "skyline_battery_current",
                "category": Category.BATTERY_INFORMATION,
                "register": ["8199", "8200"],
                "multiplier": 0.01,
                "data_type": DataType.S32.value,
                "unit_of_measurement": UnitOfElectricCurrent.AMPERE,
                "device_class": SensorDeviceClass.CURRENT,
                "state_class": SensorStateClass.MEASUREMENT,
            },
            # Offset [9-10]: Battery Load (signed int32 ÷10000 → kW)
            {
                "name": "Battery Power",
                "unique": "skyline_battery_power",
                "category": Category.BATTERY_INFORMATION,
                "register": ["8201", "8202"],
                "multiplier": 0.0001,
                "data_type": DataType.S32.value,
                "unit_of_measurement": UnitOfPower.KILO_WATT,
                "device_class": SensorDeviceClass.POWER,
                "state_class": SensorStateClass.MEASUREMENT,
            },
            # Offset [11-12]: Battery Energy In Today (U32 ÷100 → kWh)
            {
                "name": "Battery Charge Today",
                "unique": "skyline_battery_charge_today",
                "category": Category.BATTERY_INFORMATION,
                "register": ["8203", "8204"],
                "multiplier": 0.01,
                "unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR,
                "device_class": SensorDeviceClass.ENERGY,
                "state_class": SensorStateClass.TOTAL_INCREASING,
            },
            # Offset [13-14]: Battery Energy In Total (U32 ÷100 → kWh)
            {
                "name": "Battery Charge Total",
                "unique": "skyline_battery_charge_total",
                "category": Category.BATTERY_INFORMATION,
                "register": ["8205", "8206"],
                "multiplier": 0.01,
                "unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR,
                "device_class": SensorDeviceClass.ENERGY,
                "state_class": SensorStateClass.TOTAL_INCREASING,
            },
            # Offset [15-16]: Battery Energy Out Today (U32 ÷100 → kWh)
            {
                "name": "Battery Discharge Today",
                "unique": "skyline_battery_discharge_today",
                "category": Category.BATTERY_INFORMATION,
                "register": ["8207", "8208"],
                "multiplier": 0.01,
                "unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR,
                "device_class": SensorDeviceClass.ENERGY,
                "state_class": SensorStateClass.TOTAL_INCREASING,
            },
            # Offset [17-18]: Battery Energy Out Total (U32 ÷100 → kWh)
            {
                "name": "Battery Discharge Total",
                "unique": "skyline_battery_discharge_total",
                "category": Category.BATTERY_INFORMATION,
                "register": ["8209", "8210"],
                "multiplier": 0.01,
                "unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR,
                "device_class": SensorDeviceClass.ENERGY,
                "state_class": SensorStateClass.TOTAL_INCREASING,
            },
        ],
    },
]

# ---------------------------------------------------------------------------
# Shared sensor groups for Skyline (with DCDC version)
# ---------------------------------------------------------------------------
skyline_sensors = (
    skyline_identity_sensors
    + skyline_version_sensors
    + skyline_dcdc_version_sensors
    + skyline_inverter_power_sensors
    + skyline_grid_sensors
    + skyline_battery_sensors
)

# ---------------------------------------------------------------------------
# Sensor groups for Duracell G3 (same as Skyline, without DCDC version)
# ---------------------------------------------------------------------------
duracell_g3_sensors = (
    skyline_identity_sensors
    + skyline_version_sensors
    + skyline_inverter_power_sensors
    + skyline_grid_sensors
    + skyline_battery_sensors
)
