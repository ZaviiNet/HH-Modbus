"""Sigenergy ESS plant-level sensor definitions.

Credit: TypQxQ/Sigenergy-Local-Modbus (https://github.com/TypQxQ/Sigenergy-Local-Modbus)

Register map sourced from:
  TypQxQ/Sigenergy-Local-Modbus:custom_components/sigen/modbusregisterdefinitions.py

All registers are read via local Modbus TCP.
Plant-level registers start at address 30000. Despite containing read-only operational data,
Sigenergy places these in the holding register (function code 3) address space.
Gain conventions (from upstream):
  gain 1000 → multiplier 0.001  (values stored in mW/mvar → kW/kvar)
  gain 100  → multiplier 0.01   (values stored in ×100 → real unit)
  gain 10   → multiplier 0.1
"""

from homeassistant.components.sensor.const import SensorDeviceClass, SensorStateClass
from homeassistant.const import (
    PERCENTAGE,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfReactivePower,
    UnitOfTemperature,
    UnitOfTime,
)

from custom_components.hh_modbus_control.data.enums import Category, DataType, PollSpeed

# ---------------------------------------------------------------------------
# PLANT-LEVEL HOLDING REGISTER GROUPS (30000+)
# These are operational read-only data exposed in Sigenergy's holding register space.
# All groups use register_type = "holding" (Modbus function code 3).
# ---------------------------------------------------------------------------

sigenergy_plant_sensors = [
    # -------------------------------------------------------------------------
    # Group: Plant System Info & Grid Sensor (30000–30014)
    # -------------------------------------------------------------------------
    {
        "register_start": 30000,
        "poll_speed": PollSpeed.NORMAL,
        "register_type": "holding",
        "entities": [
            # 30000-30001: Plant system time (U32 epoch seconds) — read-only info
            {
                "name": "Plant System Time",
                "unique": "sigenergy_plant_system_time",
                "category": Category.BASIC_INFORMATION,
                "register": ["30000", "30001"],
                "multiplier": 1,
                "unit_of_measurement": UnitOfTime.SECONDS,
                "hidden": True,
            },
            {
                "name": "Plant Timezone Offset",
                "unique": "sigenergy_plant_timezone_offset",
                "category": Category.BASIC_INFORMATION,
                "register": ["30002"],
                "multiplier": 1,
                "data_type": DataType.S16.value,
                "unit_of_measurement": UnitOfTime.MINUTES,
                "hidden": True,
            },
            {
                "name": "EMS Work Mode",
                "unique": "sigenergy_plant_ems_work_mode",
                "category": Category.STATUS_INFORMATION,
                "register": ["30003"],
                "multiplier": 0,
            },
            {
                "name": "Grid Sensor Status",
                "unique": "sigenergy_plant_grid_sensor_status",
                "category": Category.STATUS_INFORMATION,
                "register": ["30004"],
                "multiplier": 0,
            },
            # 30005-30006: Grid active power (S32, ÷1000 → kW; >0 buy, <0 sell)
            {
                "name": "Grid Active Power",
                "unique": "sigenergy_plant_grid_active_power",
                "category": Category.GRID_CODE_INFORMATION,
                "register": ["30005", "30006"],
                "multiplier": 0.001,
                "data_type": DataType.S32.value,
                "unit_of_measurement": UnitOfPower.KILO_WATT,
                "device_class": SensorDeviceClass.POWER,
                "state_class": SensorStateClass.MEASUREMENT,
            },
            # 30007-30008: Grid reactive power (S32, ÷1000 → kvar)
            {
                "name": "Grid Reactive Power",
                "unique": "sigenergy_plant_grid_reactive_power",
                "category": Category.GRID_CODE_INFORMATION,
                "register": ["30007", "30008"],
                "multiplier": 0.001,
                "data_type": DataType.S32.value,
                "unit_of_measurement": UnitOfReactivePower.VOLT_AMPERE_REACTIVE,
                "state_class": SensorStateClass.MEASUREMENT,
                "hidden": True,
            },
            {
                "name": "On/Off Grid Status",
                "unique": "sigenergy_plant_on_off_grid_status",
                "category": Category.STATUS_INFORMATION,
                "register": ["30009"],
                "multiplier": 0,
            },
            # 30010-30011: Max active power (U32, ÷1000 → kW)
            {
                "name": "Max Active Power",
                "unique": "sigenergy_plant_max_active_power",
                "category": Category.STATUS_INFORMATION,
                "register": ["30010", "30011"],
                "multiplier": 0.001,
                "unit_of_measurement": UnitOfPower.KILO_WATT,
                "device_class": SensorDeviceClass.POWER,
                "state_class": SensorStateClass.MEASUREMENT,
                "hidden": True,
            },
            # 30012-30013: Max apparent power (U32, ÷1000 → kVA)
            {
                "name": "Max Apparent Power",
                "unique": "sigenergy_plant_max_apparent_power",
                "category": Category.STATUS_INFORMATION,
                "register": ["30012", "30013"],
                "multiplier": 0.001,
                "state_class": SensorStateClass.MEASUREMENT,
                "hidden": True,
            },
            {
                "name": "Battery SOC",
                "unique": "sigenergy_plant_ess_soc",
                "category": Category.BATTERY_INFORMATION,
                "register": ["30014"],
                "multiplier": 0.1,
                "unit_of_measurement": PERCENTAGE,
                "device_class": SensorDeviceClass.BATTERY,
                "state_class": SensorStateClass.MEASUREMENT,
            },
        ],
    },
    # -------------------------------------------------------------------------
    # Group: Phase Power & Running State (30015–30051)
    # -------------------------------------------------------------------------
    {
        "register_start": 30015,
        "poll_speed": PollSpeed.NORMAL,
        "register_type": "holding",
        "entities": [
            # 30015-30016: Phase A active power (S32, ÷1000 → kW)
            {
                "name": "Phase A Active Power",
                "unique": "sigenergy_plant_phase_a_active_power",
                "category": Category.AC_INFORMATION,
                "register": ["30015", "30016"],
                "multiplier": 0.001,
                "data_type": DataType.S32.value,
                "unit_of_measurement": UnitOfPower.KILO_WATT,
                "device_class": SensorDeviceClass.POWER,
                "state_class": SensorStateClass.MEASUREMENT,
            },
            # 30017-30018: Phase B active power
            {
                "name": "Phase B Active Power",
                "unique": "sigenergy_plant_phase_b_active_power",
                "category": Category.AC_INFORMATION,
                "register": ["30017", "30018"],
                "multiplier": 0.001,
                "data_type": DataType.S32.value,
                "unit_of_measurement": UnitOfPower.KILO_WATT,
                "device_class": SensorDeviceClass.POWER,
                "state_class": SensorStateClass.MEASUREMENT,
            },
            # 30019-30020: Phase C active power
            {
                "name": "Phase C Active Power",
                "unique": "sigenergy_plant_phase_c_active_power",
                "category": Category.AC_INFORMATION,
                "register": ["30019", "30020"],
                "multiplier": 0.001,
                "data_type": DataType.S32.value,
                "unit_of_measurement": UnitOfPower.KILO_WATT,
                "device_class": SensorDeviceClass.POWER,
                "state_class": SensorStateClass.MEASUREMENT,
            },
            # 30021-30026: Phase A/B/C reactive powers (S32 each, ÷1000 kvar)
            {
                "name": "Phase A Reactive Power",
                "unique": "sigenergy_plant_phase_a_reactive_power",
                "category": Category.AC_INFORMATION,
                "register": ["30021", "30022"],
                "multiplier": 0.001,
                "data_type": DataType.S32.value,
                "unit_of_measurement": UnitOfReactivePower.VOLT_AMPERE_REACTIVE,
                "state_class": SensorStateClass.MEASUREMENT,
                "hidden": True,
            },
            {
                "name": "Phase B Reactive Power",
                "unique": "sigenergy_plant_phase_b_reactive_power",
                "category": Category.AC_INFORMATION,
                "register": ["30023", "30024"],
                "multiplier": 0.001,
                "data_type": DataType.S32.value,
                "unit_of_measurement": UnitOfReactivePower.VOLT_AMPERE_REACTIVE,
                "state_class": SensorStateClass.MEASUREMENT,
                "hidden": True,
            },
            {
                "name": "Phase C Reactive Power",
                "unique": "sigenergy_plant_phase_c_reactive_power",
                "category": Category.AC_INFORMATION,
                "register": ["30025", "30026"],
                "multiplier": 0.001,
                "data_type": DataType.S32.value,
                "unit_of_measurement": UnitOfReactivePower.VOLT_AMPERE_REACTIVE,
                "state_class": SensorStateClass.MEASUREMENT,
                "hidden": True,
            },
            # 30027-30030: Alarm bitmasks (U16 each)
            {
                "name": "General Alarm 1",
                "unique": "sigenergy_plant_general_alarm_1",
                "category": Category.STATUS_INFORMATION,
                "register": ["30027"],
                "multiplier": 0,
                "hidden": True,
            },
            {
                "name": "General Alarm 2",
                "unique": "sigenergy_plant_general_alarm_2",
                "category": Category.STATUS_INFORMATION,
                "register": ["30028"],
                "multiplier": 0,
                "hidden": True,
            },
            {
                "name": "General Alarm 3",
                "unique": "sigenergy_plant_general_alarm_3",
                "category": Category.STATUS_INFORMATION,
                "register": ["30029"],
                "multiplier": 0,
                "hidden": True,
            },
            {
                "name": "General Alarm 4",
                "unique": "sigenergy_plant_general_alarm_4",
                "category": Category.STATUS_INFORMATION,
                "register": ["30030"],
                "multiplier": 0,
                "hidden": True,
            },
            # 30031-30032: Total plant active power (S32, ÷1000 → kW)
            {
                "name": "Plant Active Power",
                "unique": "sigenergy_plant_active_power",
                "category": Category.AC_INFORMATION,
                "register": ["30031", "30032"],
                "multiplier": 0.001,
                "data_type": DataType.S32.value,
                "unit_of_measurement": UnitOfPower.KILO_WATT,
                "device_class": SensorDeviceClass.POWER,
                "state_class": SensorStateClass.MEASUREMENT,
            },
            # 30033-30034: Plant reactive power
            {
                "name": "Plant Reactive Power",
                "unique": "sigenergy_plant_reactive_power",
                "category": Category.AC_INFORMATION,
                "register": ["30033", "30034"],
                "multiplier": 0.001,
                "data_type": DataType.S32.value,
                "unit_of_measurement": UnitOfReactivePower.VOLT_AMPERE_REACTIVE,
                "state_class": SensorStateClass.MEASUREMENT,
                "hidden": True,
            },
            # 30035-30036: PV power (S32, ÷1000 → kW)
            {
                "name": "PV Power",
                "unique": "sigenergy_plant_pv_power",
                "category": Category.PV_INFORMATION,
                "register": ["30035", "30036"],
                "multiplier": 0.001,
                "data_type": DataType.S32.value,
                "unit_of_measurement": UnitOfPower.KILO_WATT,
                "device_class": SensorDeviceClass.POWER,
                "state_class": SensorStateClass.MEASUREMENT,
            },
            # 30037-30038: ESS power (S32, ÷1000 → kW; <0 discharge, >0 charge)
            {
                "name": "Battery Power",
                "unique": "sigenergy_plant_ess_power",
                "category": Category.BATTERY_INFORMATION,
                "register": ["30037", "30038"],
                "multiplier": 0.001,
                "data_type": DataType.S32.value,
                "unit_of_measurement": UnitOfPower.KILO_WATT,
                "device_class": SensorDeviceClass.POWER,
                "state_class": SensorStateClass.MEASUREMENT,
            },
            # 30039-30050: Available power limits (U32/S32, hidden operational data)
            {
                "name": "Available Max Active Power",
                "unique": "sigenergy_plant_avail_max_active_power",
                "category": Category.STATUS_INFORMATION,
                "register": ["30039", "30040"],
                "multiplier": 0.001,
                "unit_of_measurement": UnitOfPower.KILO_WATT,
                "device_class": SensorDeviceClass.POWER,
                "state_class": SensorStateClass.MEASUREMENT,
                "hidden": True,
            },
            {
                "name": "Available Min Active Power",
                "unique": "sigenergy_plant_avail_min_active_power",
                "category": Category.STATUS_INFORMATION,
                "register": ["30041", "30042"],
                "multiplier": 0.001,
                "data_type": DataType.S32.value,
                "unit_of_measurement": UnitOfPower.KILO_WATT,
                "device_class": SensorDeviceClass.POWER,
                "state_class": SensorStateClass.MEASUREMENT,
                "hidden": True,
            },
            {
                "name": "reserve_30043",
                "unique": "sigenergy_reserve_30043",
                "register": ["30043"],
                "multiplier": 0,
                "hidden": True,
            },
            {
                "name": "reserve_30044",
                "unique": "sigenergy_reserve_30044",
                "register": ["30044"],
                "multiplier": 0,
                "hidden": True,
            },
            {
                "name": "reserve_30045",
                "unique": "sigenergy_reserve_30045",
                "register": ["30045"],
                "multiplier": 0,
                "hidden": True,
            },
            {
                "name": "reserve_30046",
                "unique": "sigenergy_reserve_30046",
                "register": ["30046"],
                "multiplier": 0,
                "hidden": True,
            },
            # 30047-30048: Max charging power (U32, ÷1000 → kW)
            {
                "name": "Max Charging Power",
                "unique": "sigenergy_plant_max_charging_power",
                "category": Category.BATTERY_INFORMATION,
                "register": ["30047", "30048"],
                "multiplier": 0.001,
                "unit_of_measurement": UnitOfPower.KILO_WATT,
                "device_class": SensorDeviceClass.POWER,
                "state_class": SensorStateClass.MEASUREMENT,
            },
            # 30049-30050: Max discharging power (U32, ÷1000 → kW)
            {
                "name": "Max Discharging Power",
                "unique": "sigenergy_plant_max_discharging_power",
                "category": Category.BATTERY_INFORMATION,
                "register": ["30049", "30050"],
                "multiplier": 0.001,
                "unit_of_measurement": UnitOfPower.KILO_WATT,
                "device_class": SensorDeviceClass.POWER,
                "state_class": SensorStateClass.MEASUREMENT,
            },
            {
                "name": "Plant Running State",
                "unique": "sigenergy_plant_running_state",
                "category": Category.STATUS_INFORMATION,
                "register": ["30051"],
                "multiplier": 0,
            },
        ],
    },
    # -------------------------------------------------------------------------
    # Group: Energy Totals (30064–30093)
    # -------------------------------------------------------------------------
    {
        "register_start": 30064,
        "poll_speed": PollSpeed.SLOW,
        "register_type": "holding",
        "entities": [
            # 30064-30065: Max charging capacity (U32, ÷100 → kWh)
            {
                "name": "Max Charging Capacity",
                "unique": "sigenergy_plant_max_charging_capacity",
                "category": Category.BATTERY_INFORMATION,
                "register": ["30064", "30065"],
                "multiplier": 0.01,
                "unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR,
                "device_class": SensorDeviceClass.ENERGY,
                "state_class": SensorStateClass.TOTAL,
                "hidden": True,
            },
            # 30066-30067: Max discharging capacity (U32, ÷100 → kWh)
            {
                "name": "Max Discharging Capacity",
                "unique": "sigenergy_plant_max_discharging_capacity",
                "category": Category.BATTERY_INFORMATION,
                "register": ["30066", "30067"],
                "multiplier": 0.01,
                "unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR,
                "device_class": SensorDeviceClass.ENERGY,
                "state_class": SensorStateClass.TOTAL,
                "hidden": True,
            },
            # 30068-30069: Rated charging power
            {
                "name": "Rated Charging Power",
                "unique": "sigenergy_plant_rated_charging_power",
                "category": Category.BATTERY_INFORMATION,
                "register": ["30068", "30069"],
                "multiplier": 0.001,
                "unit_of_measurement": UnitOfPower.KILO_WATT,
                "device_class": SensorDeviceClass.POWER,
                "state_class": SensorStateClass.MEASUREMENT,
                "hidden": True,
            },
            # 30070-30071: Rated discharging power
            {
                "name": "Rated Discharging Power",
                "unique": "sigenergy_plant_rated_discharging_power",
                "category": Category.BATTERY_INFORMATION,
                "register": ["30070", "30071"],
                "multiplier": 0.001,
                "unit_of_measurement": UnitOfPower.KILO_WATT,
                "device_class": SensorDeviceClass.POWER,
                "state_class": SensorStateClass.MEASUREMENT,
                "hidden": True,
            },
            # 30072-30082: reserved padding
            {
                "name": "reserve_30072",
                "unique": "sigenergy_reserve_30072",
                "register": ["30072"],
                "multiplier": 0,
                "hidden": True,
            },
            {
                "name": "reserve_30073",
                "unique": "sigenergy_reserve_30073",
                "register": ["30073"],
                "multiplier": 0,
                "hidden": True,
            },
            {
                "name": "reserve_30074",
                "unique": "sigenergy_reserve_30074",
                "register": ["30074"],
                "multiplier": 0,
                "hidden": True,
            },
            {
                "name": "reserve_30075",
                "unique": "sigenergy_reserve_30075",
                "register": ["30075"],
                "multiplier": 0,
                "hidden": True,
            },
            {
                "name": "reserve_30076",
                "unique": "sigenergy_reserve_30076",
                "register": ["30076"],
                "multiplier": 0,
                "hidden": True,
            },
            {
                "name": "reserve_30077",
                "unique": "sigenergy_reserve_30077",
                "register": ["30077"],
                "multiplier": 0,
                "hidden": True,
            },
            {
                "name": "reserve_30078",
                "unique": "sigenergy_reserve_30078",
                "register": ["30078"],
                "multiplier": 0,
                "hidden": True,
            },
            {
                "name": "reserve_30079",
                "unique": "sigenergy_reserve_30079",
                "register": ["30079"],
                "multiplier": 0,
                "hidden": True,
            },
            {
                "name": "reserve_30080",
                "unique": "sigenergy_reserve_30080",
                "register": ["30080"],
                "multiplier": 0,
                "hidden": True,
            },
            {
                "name": "reserve_30081",
                "unique": "sigenergy_reserve_30081",
                "register": ["30081"],
                "multiplier": 0,
                "hidden": True,
            },
            {
                "name": "reserve_30082",
                "unique": "sigenergy_reserve_30082",
                "register": ["30082"],
                "multiplier": 0,
                "hidden": True,
            },
            # 30083-30084: Rated energy capacity (U32, ÷100 → kWh)
            {
                "name": "Battery Rated Energy Capacity",
                "unique": "sigenergy_plant_rated_energy_capacity",
                "category": Category.BATTERY_INFORMATION,
                "register": ["30083", "30084"],
                "multiplier": 0.01,
                "unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR,
                "device_class": SensorDeviceClass.ENERGY,
                "state_class": SensorStateClass.TOTAL,
            },
            {
                "name": "Battery Charge Cut-off SOC",
                "unique": "sigenergy_plant_charge_cutoff_soc",
                "category": Category.BATTERY_INFORMATION,
                "register": ["30085"],
                "multiplier": 0.1,
                "unit_of_measurement": PERCENTAGE,
                "device_class": SensorDeviceClass.BATTERY,
                "state_class": SensorStateClass.MEASUREMENT,
            },
            {
                "name": "Battery Discharge Cut-off SOC",
                "unique": "sigenergy_plant_discharge_cutoff_soc",
                "category": Category.BATTERY_INFORMATION,
                "register": ["30086"],
                "multiplier": 0.1,
                "unit_of_measurement": PERCENTAGE,
                "device_class": SensorDeviceClass.BATTERY,
                "state_class": SensorStateClass.MEASUREMENT,
            },
            {
                "name": "Battery State of Health",
                "unique": "sigenergy_plant_ess_soh",
                "category": Category.BATTERY_INFORMATION,
                "register": ["30087"],
                "multiplier": 0.1,
                "unit_of_measurement": PERCENTAGE,
                "state_class": SensorStateClass.MEASUREMENT,
            },
            # 30088-30091: Total PV energy (U64 split into 4 regs, ÷100 → kWh)
            # We read only the low 32-bit word for practical purposes
            {
                "name": "Total PV Energy",
                "unique": "sigenergy_plant_accumulated_pv_energy",
                "category": Category.PV_INFORMATION,
                "register": ["30088", "30089"],
                "multiplier": 0.01,
                "unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR,
                "device_class": SensorDeviceClass.ENERGY,
                "state_class": SensorStateClass.TOTAL_INCREASING,
            },
            {
                "name": "reserve_30090",
                "unique": "sigenergy_reserve_30090",
                "register": ["30090"],
                "multiplier": 0,
                "hidden": True,
            },
            {
                "name": "reserve_30091",
                "unique": "sigenergy_reserve_30091",
                "register": ["30091"],
                "multiplier": 0,
                "hidden": True,
            },
            # 30092-30093: Daily consumed energy (U32, ÷100 → kWh)
            {
                "name": "Today Consumed Energy",
                "unique": "sigenergy_plant_daily_consumed_energy",
                "category": Category.ENERGY_DATA,
                "register": ["30092", "30093"],
                "multiplier": 0.01,
                "unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR,
                "device_class": SensorDeviceClass.ENERGY,
                "state_class": SensorStateClass.TOTAL_INCREASING,
            },
        ],
    },
    # -------------------------------------------------------------------------
    # Group: Accumulated Battery & Grid Energy (30200–30223)
    # -------------------------------------------------------------------------
    {
        "register_start": 30200,
        "poll_speed": PollSpeed.SLOW,
        "register_type": "holding",
        "entities": [
            # 30200-30203: Accumulated battery charge energy (U64 low 32-bit word, ÷100 → kWh)
            {
                "name": "Total Battery Charge Energy",
                "unique": "sigenergy_plant_accumulated_battery_charge",
                "category": Category.BATTERY_INFORMATION,
                "register": ["30200", "30201"],
                "multiplier": 0.01,
                "unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR,
                "device_class": SensorDeviceClass.ENERGY,
                "state_class": SensorStateClass.TOTAL_INCREASING,
            },
            {
                "name": "reserve_30202",
                "unique": "sigenergy_reserve_30202",
                "register": ["30202"],
                "multiplier": 0,
                "hidden": True,
            },
            {
                "name": "reserve_30203",
                "unique": "sigenergy_reserve_30203",
                "register": ["30203"],
                "multiplier": 0,
                "hidden": True,
            },
            # 30204-30207: Accumulated battery discharge energy
            {
                "name": "Total Battery Discharge Energy",
                "unique": "sigenergy_plant_accumulated_battery_discharge",
                "category": Category.BATTERY_INFORMATION,
                "register": ["30204", "30205"],
                "multiplier": 0.01,
                "unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR,
                "device_class": SensorDeviceClass.ENERGY,
                "state_class": SensorStateClass.TOTAL_INCREASING,
            },
            {
                "name": "reserve_30206",
                "unique": "sigenergy_reserve_30206",
                "register": ["30206"],
                "multiplier": 0,
                "hidden": True,
            },
            {
                "name": "reserve_30207",
                "unique": "sigenergy_reserve_30207",
                "register": ["30207"],
                "multiplier": 0,
                "hidden": True,
            },
            # 30208-30215: reserved
            {
                "name": "reserve_30208",
                "unique": "sigenergy_reserve_30208",
                "register": ["30208"],
                "multiplier": 0,
                "hidden": True,
            },
            {
                "name": "reserve_30209",
                "unique": "sigenergy_reserve_30209",
                "register": ["30209"],
                "multiplier": 0,
                "hidden": True,
            },
            {
                "name": "reserve_30210",
                "unique": "sigenergy_reserve_30210",
                "register": ["30210"],
                "multiplier": 0,
                "hidden": True,
            },
            {
                "name": "reserve_30211",
                "unique": "sigenergy_reserve_30211",
                "register": ["30211"],
                "multiplier": 0,
                "hidden": True,
            },
            {
                "name": "reserve_30212",
                "unique": "sigenergy_reserve_30212",
                "register": ["30212"],
                "multiplier": 0,
                "hidden": True,
            },
            {
                "name": "reserve_30213",
                "unique": "sigenergy_reserve_30213",
                "register": ["30213"],
                "multiplier": 0,
                "hidden": True,
            },
            {
                "name": "reserve_30214",
                "unique": "sigenergy_reserve_30214",
                "register": ["30214"],
                "multiplier": 0,
                "hidden": True,
            },
            {
                "name": "reserve_30215",
                "unique": "sigenergy_reserve_30215",
                "register": ["30215"],
                "multiplier": 0,
                "hidden": True,
            },
            # 30216-30219: Accumulated grid import energy (U64, ÷100 → kWh)
            {
                "name": "Total Grid Import Energy",
                "unique": "sigenergy_plant_accumulated_grid_import",
                "category": Category.ENERGY_DATA,
                "register": ["30216", "30217"],
                "multiplier": 0.01,
                "unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR,
                "device_class": SensorDeviceClass.ENERGY,
                "state_class": SensorStateClass.TOTAL_INCREASING,
            },
            {
                "name": "reserve_30218",
                "unique": "sigenergy_reserve_30218",
                "register": ["30218"],
                "multiplier": 0,
                "hidden": True,
            },
            {
                "name": "reserve_30219",
                "unique": "sigenergy_reserve_30219",
                "register": ["30219"],
                "multiplier": 0,
                "hidden": True,
            },
            # 30220-30223: Accumulated grid export energy (U64, ÷100 → kWh)
            {
                "name": "Total Grid Export Energy",
                "unique": "sigenergy_plant_accumulated_grid_export",
                "category": Category.ENERGY_DATA,
                "register": ["30220", "30221"],
                "multiplier": 0.01,
                "unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR,
                "device_class": SensorDeviceClass.ENERGY,
                "state_class": SensorStateClass.TOTAL_INCREASING,
            },
            {
                "name": "reserve_30222",
                "unique": "sigenergy_reserve_30222",
                "register": ["30222"],
                "multiplier": 0,
                "hidden": True,
            },
            {
                "name": "reserve_30223",
                "unique": "sigenergy_reserve_30223",
                "register": ["30223"],
                "multiplier": 0,
                "hidden": True,
            },
        ],
    },
]

# Combined list exposed to the integration loader
sigenergy_sensors = sigenergy_plant_sensors
