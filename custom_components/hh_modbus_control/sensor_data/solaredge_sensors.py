"""SolarEdge inverter sensor definitions (SunSpec Modbus).

Credit: binsentsu/home-assistant-solaredge-modbus
        (https://github.com/binsentsu/home-assistant-solaredge-modbus)

Register map sourced from:
  binsentsu/home-assistant-solaredge-modbus:custom_components/solaredge_modbus/__init__.py
  binsentsu/home-assistant-solaredge-modbus:custom_components/solaredge_modbus/const.py

SolarEdge inverters use Modbus TCP on port 1502 (slave address 1 by default).
Registers follow the SunSpec standard at the 40000+ address block.
StorEdge battery registers are in the 0xE000+ (57344+) proprietary block.

Scale factors:
  SunSpec stores a scale factor register alongside each value register.
  For simplicity, this implementation uses fixed multipliers that match
  the typical scale factor applied by SolarEdge production inverters.
  If your readings appear off by a power of 10, verify the scale factor
  registers (e.g. 40075 for current, 40082 for voltage, 40084 for power).
"""

from homeassistant.components.sensor.const import SensorDeviceClass, SensorStateClass
from homeassistant.const import (
    PERCENTAGE,
    UnitOfApparentPower,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfTemperature,
)

from custom_components.hh_modbus_control.data.enums import Category, DataType, PollSpeed

# ---------------------------------------------------------------------------
# DEVICE INFO (read once at startup) — 40004–40067
# SunSpec Common Block: manufacturer(32B), model(32B), pad(16B), version(16B), serial(32B)
# Each register holds 2 ASCII bytes; 32B = 16 registers.
# ---------------------------------------------------------------------------

solaredge_info_sensors = [
    {
        "register_start": 40004,
        "poll_speed": PollSpeed.ONCE,
        "register_type": "holding",
        "entities": [
            # 40004-40019: Manufacturer string (16 registers = 32 chars)
            {
                "name": "Manufacturer",
                "unique": "solaredge_manufacturer",
                "category": Category.BASIC_INFORMATION,
                "register": [str(r) for r in range(40004, 40020)],
                "multiplier": 0,
            },
            # 40020-40035: Model string (16 registers)
            {
                "name": "Model",
                "unique": "solaredge_model",
                "category": Category.BASIC_INFORMATION,
                "register": [str(r) for r in range(40020, 40036)],
                "multiplier": 0,
            },
            # 40036-40043: Version string (8 registers = 16 chars)
            {
                "name": "Firmware Version",
                "unique": "solaredge_firmware_version",
                "category": Category.BASIC_INFORMATION,
                "register": [str(r) for r in range(40036, 40044)],
                "multiplier": 0,
                "hidden": True,
            },
            # 40044-40059: Serial number (16 registers = 32 chars)
            {
                "name": "Serial Number",
                "unique": "solaredge_serial_number",
                "category": Category.BASIC_INFORMATION,
                "register": [str(r) for r in range(40044, 40060)],
                "multiplier": 0,
            },
            # 40060: Device address (U16)
            {
                "name": "Device Address",
                "unique": "solaredge_device_address",
                "category": Category.BASIC_INFORMATION,
                "register": ["40060"],
                "multiplier": 0,
                "hidden": True,
            },
        ],
    },
]

# ---------------------------------------------------------------------------
# INVERTER REGISTERS (40071–40108) — live data, fast poll
# SunSpec Inverter Model — AC and DC measurements
# ---------------------------------------------------------------------------

solaredge_inverter_sensors = [
    {
        "register_start": 40071,
        "poll_speed": PollSpeed.FAST,
        "register_type": "holding",
        "entities": [
            # 40071: AC Total Current (A × SF at 40075; SF typically -1 → ×0.1)
            {
                "name": "AC Current",
                "unique": "solaredge_ac_current",
                "category": Category.AC_INFORMATION,
                "register": ["40071"],
                "multiplier": 0.1,
                "unit_of_measurement": UnitOfElectricCurrent.AMPERE,
                "device_class": SensorDeviceClass.CURRENT,
                "state_class": SensorStateClass.MEASUREMENT,
            },
            # 40072: Phase A current
            {
                "name": "Phase A Current",
                "unique": "solaredge_phase_a_current",
                "category": Category.AC_INFORMATION,
                "register": ["40072"],
                "multiplier": 0.1,
                "unit_of_measurement": UnitOfElectricCurrent.AMPERE,
                "device_class": SensorDeviceClass.CURRENT,
                "state_class": SensorStateClass.MEASUREMENT,
            },
            # 40073: Phase B current
            {
                "name": "Phase B Current",
                "unique": "solaredge_phase_b_current",
                "category": Category.AC_INFORMATION,
                "register": ["40073"],
                "multiplier": 0.1,
                "unit_of_measurement": UnitOfElectricCurrent.AMPERE,
                "device_class": SensorDeviceClass.CURRENT,
                "state_class": SensorStateClass.MEASUREMENT,
            },
            # 40074: Phase C current
            {
                "name": "Phase C Current",
                "unique": "solaredge_phase_c_current",
                "category": Category.AC_INFORMATION,
                "register": ["40074"],
                "multiplier": 0.1,
                "unit_of_measurement": UnitOfElectricCurrent.AMPERE,
                "device_class": SensorDeviceClass.CURRENT,
                "state_class": SensorStateClass.MEASUREMENT,
            },
            # 40075: Current scale factor (hidden internal)
            {
                "name": "AC Current Scale Factor",
                "unique": "solaredge_ac_current_sf",
                "register": ["40075"],
                "multiplier": 0,
                "hidden": True,
            },
            # 40076: AB voltage
            {
                "name": "Voltage AB",
                "unique": "solaredge_voltage_ab",
                "category": Category.AC_INFORMATION,
                "register": ["40076"],
                "multiplier": 0.1,
                "unit_of_measurement": UnitOfElectricPotential.VOLT,
                "device_class": SensorDeviceClass.VOLTAGE,
                "state_class": SensorStateClass.MEASUREMENT,
            },
            # 40077: BC voltage
            {
                "name": "Voltage BC",
                "unique": "solaredge_voltage_bc",
                "category": Category.AC_INFORMATION,
                "register": ["40077"],
                "multiplier": 0.1,
                "unit_of_measurement": UnitOfElectricPotential.VOLT,
                "device_class": SensorDeviceClass.VOLTAGE,
                "state_class": SensorStateClass.MEASUREMENT,
            },
            # 40078: CA voltage
            {
                "name": "Voltage CA",
                "unique": "solaredge_voltage_ca",
                "category": Category.AC_INFORMATION,
                "register": ["40078"],
                "multiplier": 0.1,
                "unit_of_measurement": UnitOfElectricPotential.VOLT,
                "device_class": SensorDeviceClass.VOLTAGE,
                "state_class": SensorStateClass.MEASUREMENT,
            },
            # 40079: Phase A-N voltage
            {
                "name": "Phase A Voltage",
                "unique": "solaredge_phase_a_voltage",
                "category": Category.AC_INFORMATION,
                "register": ["40079"],
                "multiplier": 0.1,
                "unit_of_measurement": UnitOfElectricPotential.VOLT,
                "device_class": SensorDeviceClass.VOLTAGE,
                "state_class": SensorStateClass.MEASUREMENT,
            },
            # 40080: Phase B-N voltage
            {
                "name": "Phase B Voltage",
                "unique": "solaredge_phase_b_voltage",
                "category": Category.AC_INFORMATION,
                "register": ["40080"],
                "multiplier": 0.1,
                "unit_of_measurement": UnitOfElectricPotential.VOLT,
                "device_class": SensorDeviceClass.VOLTAGE,
                "state_class": SensorStateClass.MEASUREMENT,
            },
            # 40081: Phase C-N voltage
            {
                "name": "Phase C Voltage",
                "unique": "solaredge_phase_c_voltage",
                "category": Category.AC_INFORMATION,
                "register": ["40081"],
                "multiplier": 0.1,
                "unit_of_measurement": UnitOfElectricPotential.VOLT,
                "device_class": SensorDeviceClass.VOLTAGE,
                "state_class": SensorStateClass.MEASUREMENT,
            },
            # 40082: Voltage scale factor (hidden)
            {
                "name": "AC Voltage Scale Factor",
                "unique": "solaredge_ac_voltage_sf",
                "register": ["40082"],
                "multiplier": 0,
                "hidden": True,
            },
            # 40083: AC Power (int16, W × SF at 40084; SF typically -1 → ×0.1 = W)
            {
                "name": "AC Power",
                "unique": "solaredge_ac_power",
                "category": Category.AC_INFORMATION,
                "register": ["40083"],
                "multiplier": 1,
                "data_type": DataType.S16.value,
                "unit_of_measurement": UnitOfPower.WATT,
                "device_class": SensorDeviceClass.POWER,
                "state_class": SensorStateClass.MEASUREMENT,
            },
            # 40084: Power scale factor (hidden)
            {
                "name": "AC Power Scale Factor",
                "unique": "solaredge_ac_power_sf",
                "register": ["40084"],
                "multiplier": 0,
                "hidden": True,
            },
            # 40085: Frequency (Hz × SF; SF typically -2 → ×0.01)
            {
                "name": "AC Frequency",
                "unique": "solaredge_ac_frequency",
                "category": Category.AC_INFORMATION,
                "register": ["40085"],
                "multiplier": 0.01,
                "unit_of_measurement": UnitOfFrequency.HERTZ,
                "device_class": SensorDeviceClass.FREQUENCY,
                "state_class": SensorStateClass.MEASUREMENT,
            },
            # 40086: Frequency scale factor (hidden)
            {
                "name": "AC Frequency Scale Factor",
                "unique": "solaredge_ac_freq_sf",
                "register": ["40086"],
                "multiplier": 0,
                "hidden": True,
            },
            # 40087: Apparent power (VA × SF)
            {
                "name": "Apparent Power",
                "unique": "solaredge_apparent_power",
                "category": Category.AC_INFORMATION,
                "register": ["40087"],
                "multiplier": 1,
                "data_type": DataType.S16.value,
                "unit_of_measurement": UnitOfApparentPower.VOLT_AMPERE,
                "state_class": SensorStateClass.MEASUREMENT,
            },
            # 40088: Apparent power scale factor (hidden)
            {
                "name": "Apparent Power Scale Factor",
                "unique": "solaredge_apparent_power_sf",
                "register": ["40088"],
                "multiplier": 0,
                "hidden": True,
            },
            # 40089: Reactive power (VAR × SF)
            {
                "name": "Reactive Power",
                "unique": "solaredge_reactive_power",
                "category": Category.AC_INFORMATION,
                "register": ["40089"],
                "multiplier": 1,
                "data_type": DataType.S16.value,
                "state_class": SensorStateClass.MEASUREMENT,
            },
            # 40090: Reactive power scale factor (hidden)
            {
                "name": "Reactive Power Scale Factor",
                "unique": "solaredge_reactive_power_sf",
                "register": ["40090"],
                "multiplier": 0,
                "hidden": True,
            },
            # 40091: Power factor (% × SF; SF typically -2 → ×0.01)
            {
                "name": "Power Factor",
                "unique": "solaredge_power_factor",
                "category": Category.AC_INFORMATION,
                "register": ["40091"],
                "multiplier": 0.01,
                "data_type": DataType.S16.value,
                "unit_of_measurement": PERCENTAGE,
                "state_class": SensorStateClass.MEASUREMENT,
            },
            # 40092: Power factor scale factor (hidden)
            {
                "name": "Power Factor Scale Factor",
                "unique": "solaredge_power_factor_sf",
                "register": ["40092"],
                "multiplier": 0,
                "hidden": True,
            },
            # 40093-40094: AC Energy (U32, Wh × SF; typically SF=-3 → ÷1000 = kWh)
            {
                "name": "AC Energy Total",
                "unique": "solaredge_ac_energy_total",
                "category": Category.ENERGY_DATA,
                "register": ["40093", "40094"],
                "multiplier": 0.001,
                "unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR,
                "device_class": SensorDeviceClass.ENERGY,
                "state_class": SensorStateClass.TOTAL_INCREASING,
            },
            # 40095: AC Energy scale factor (hidden)
            {
                "name": "AC Energy Scale Factor",
                "unique": "solaredge_ac_energy_sf",
                "register": ["40095"],
                "multiplier": 0,
                "hidden": True,
            },
            # 40096: DC Current (A × SF; SF typically -2 → ×0.01)
            {
                "name": "DC Current",
                "unique": "solaredge_dc_current",
                "category": Category.PV_INFORMATION,
                "register": ["40096"],
                "multiplier": 0.01,
                "unit_of_measurement": UnitOfElectricCurrent.AMPERE,
                "device_class": SensorDeviceClass.CURRENT,
                "state_class": SensorStateClass.MEASUREMENT,
            },
            # 40097: DC Current scale factor (hidden)
            {
                "name": "DC Current Scale Factor",
                "unique": "solaredge_dc_current_sf",
                "register": ["40097"],
                "multiplier": 0,
                "hidden": True,
            },
            # 40098: DC Voltage (V × SF; SF typically -1 → ×0.1)
            {
                "name": "DC Voltage",
                "unique": "solaredge_dc_voltage",
                "category": Category.PV_INFORMATION,
                "register": ["40098"],
                "multiplier": 0.1,
                "unit_of_measurement": UnitOfElectricPotential.VOLT,
                "device_class": SensorDeviceClass.VOLTAGE,
                "state_class": SensorStateClass.MEASUREMENT,
            },
            # 40099: DC Voltage scale factor (hidden)
            {
                "name": "DC Voltage Scale Factor",
                "unique": "solaredge_dc_voltage_sf",
                "register": ["40099"],
                "multiplier": 0,
                "hidden": True,
            },
            # 40100: DC Power (W × SF; SF typically -1 → ×0.1)
            {
                "name": "DC Power",
                "unique": "solaredge_dc_power",
                "category": Category.PV_INFORMATION,
                "register": ["40100"],
                "multiplier": 1,
                "data_type": DataType.S16.value,
                "unit_of_measurement": UnitOfPower.WATT,
                "device_class": SensorDeviceClass.POWER,
                "state_class": SensorStateClass.MEASUREMENT,
            },
            # 40101: DC Power scale factor (hidden)
            {
                "name": "DC Power Scale Factor",
                "unique": "solaredge_dc_power_sf",
                "register": ["40101"],
                "multiplier": 0,
                "hidden": True,
            },
            # 40102: reserved
            {
                "name": "reserve_40102",
                "unique": "solaredge_reserve_40102",
                "register": ["40102"],
                "multiplier": 0,
                "hidden": True,
            },
            # 40103: Heatsink temperature (°C × SF; SF typically -2 → ×0.01)
            {
                "name": "Heatsink Temperature",
                "unique": "solaredge_heatsink_temp",
                "category": Category.STATUS_INFORMATION,
                "register": ["40103"],
                "multiplier": 0.01,
                "data_type": DataType.S16.value,
                "unit_of_measurement": UnitOfTemperature.CELSIUS,
                "device_class": SensorDeviceClass.TEMPERATURE,
                "state_class": SensorStateClass.MEASUREMENT,
            },
            # 40104: reserved
            {
                "name": "reserve_40104",
                "unique": "solaredge_reserve_40104",
                "register": ["40104"],
                "multiplier": 0,
                "hidden": True,
            },
            # 40105: reserved
            {
                "name": "reserve_40105",
                "unique": "solaredge_reserve_40105",
                "register": ["40105"],
                "multiplier": 0,
                "hidden": True,
            },
            # 40106: Temperature scale factor (hidden)
            {
                "name": "Temperature Scale Factor",
                "unique": "solaredge_temp_sf",
                "register": ["40106"],
                "multiplier": 0,
                "hidden": True,
            },
            # 40107: Inverter status (1=Off, 2=Sleeping, 3=Starting, 4=Producing, 5=Throttled, 6=ShuttingDown, 7=Fault, 8=Standby)
            {
                "name": "Inverter Status",
                "unique": "solaredge_inverter_status",
                "category": Category.STATUS_INFORMATION,
                "register": ["40107"],
                "multiplier": 0,
            },
            # 40108: Vendor status (model-specific, hidden)
            {
                "name": "Vendor Status",
                "unique": "solaredge_vendor_status",
                "category": Category.STATUS_INFORMATION,
                "register": ["40108"],
                "multiplier": 0,
                "hidden": True,
            },
        ],
    },
]

# Combined sensor list
solaredge_sensors = solaredge_info_sensors + solaredge_inverter_sensors
