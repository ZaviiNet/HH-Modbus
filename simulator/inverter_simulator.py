#!/usr/bin/env python3
"""
Inverter Modbus TCP simulator for hh_modbus_control.

Simulates any supported inverter brand by serving realistic Modbus register
values over a TCP socket. Designed to test the hh_modbus_control Home
Assistant integration without physical hardware.

How to run (from the repository root):
    python simulator/inverter_simulator.py --brand solis
    python simulator/inverter_simulator.py --brand givenergy --port 8899
    python simulator/inverter_simulator.py --brand sunsynk --host 0.0.0.0
    python simulator/inverter_simulator.py --brand solaredge --port 1502
    python simulator/inverter_simulator.py --brand skyline --verbose

Supported brands:
    solis, sunsynk, deye, givenergy, sigenergy, solaredge, skyline, duracell
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
import types

# ---------------------------------------------------------------------------
# Path setup — add repo root so custom_components modules are importable
# ---------------------------------------------------------------------------
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

# ---------------------------------------------------------------------------
# Mock the homeassistant package so sensor_data modules can be imported
# without a running Home Assistant instance.
# ---------------------------------------------------------------------------


def _register_mock_module(name: str, **attrs: object) -> types.ModuleType:
    mod = types.ModuleType(name)
    for k, v in attrs.items():
        setattr(mod, k, v)
    sys.modules[name] = mod
    return mod


class _SensorDeviceClass:
    BATTERY = "battery"
    CURRENT = "current"
    ENERGY = "energy"
    FREQUENCY = "frequency"
    POWER = "power"
    POWER_FACTOR = "power_factor"
    TEMPERATURE = "temperature"
    TIMESTAMP = "timestamp"
    VOLTAGE = "voltage"
    APPARENT_POWER = "apparent_power"
    REACTIVE_POWER = "reactive_power"
    DURATION = "duration"


class _SensorStateClass:
    MEASUREMENT = "measurement"
    TOTAL = "total"
    TOTAL_INCREASING = "total_increasing"


class _UnitOfElectricCurrent:
    AMPERE = "A"


class _UnitOfElectricPotential:
    VOLT = "V"


class _UnitOfEnergy:
    KILO_WATT_HOUR = "kWh"
    WATT_HOUR = "Wh"


class _UnitOfFrequency:
    HERTZ = "Hz"


class _UnitOfPower:
    WATT = "W"
    KILO_WATT = "kW"


class _UnitOfTemperature:
    CELSIUS = "°C"


class _UnitOfTime:
    SECONDS = "s"
    MINUTES = "min"
    HOURS = "h"


class _UnitOfApparentPower:
    VOLT_AMPERE = "VA"


class _UnitOfReactivePower:
    VOLT_AMPERE_REACTIVE = "var"


# Register mock modules before any sensor_data imports.
# We must also stub out the hh_modbus_control package itself (and its
# dependencies) so Python does not try to execute __init__.py, which
# requires voluptuous, homeassistant.core, etc.
_register_mock_module("homeassistant")
_register_mock_module("homeassistant.components")
_register_mock_module("homeassistant.components.sensor")
_register_mock_module(
    "homeassistant.components.sensor.const",
    SensorDeviceClass=_SensorDeviceClass,
    SensorStateClass=_SensorStateClass,
)
_register_mock_module(
    "homeassistant.const",
    PERCENTAGE="%",
    UnitOfElectricCurrent=_UnitOfElectricCurrent,
    UnitOfElectricPotential=_UnitOfElectricPotential,
    UnitOfEnergy=_UnitOfEnergy,
    UnitOfFrequency=_UnitOfFrequency,
    UnitOfPower=_UnitOfPower,
    UnitOfTemperature=_UnitOfTemperature,
    UnitOfTime=_UnitOfTime,
    UnitOfApparentPower=_UnitOfApparentPower,
    UnitOfReactivePower=_UnitOfReactivePower,
)
# Stub the integration package so its __init__.py is never executed.
# We must set __path__ on the package stubs so Python can still find
# their submodules (data.enums, sensor_data.*) on disk.
_HH_ROOT = os.path.join(_REPO_ROOT, "custom_components", "hh_modbus_control")
_register_mock_module("custom_components")

_hh_pkg = _register_mock_module("custom_components.hh_modbus_control")
_hh_pkg.__path__ = [_HH_ROOT]
_hh_pkg.__package__ = "custom_components.hh_modbus_control"

_hh_data = _register_mock_module("custom_components.hh_modbus_control.data")
_hh_data.__path__ = [os.path.join(_HH_ROOT, "data")]
_hh_data.__package__ = "custom_components.hh_modbus_control.data"

_hh_sd = _register_mock_module("custom_components.hh_modbus_control.sensor_data")
_hh_sd.__path__ = [os.path.join(_HH_ROOT, "sensor_data")]
_hh_sd.__package__ = "custom_components.hh_modbus_control.sensor_data"

# ---------------------------------------------------------------------------
# Import sensor definitions (HA mocks must be in sys.modules first)
# ---------------------------------------------------------------------------
# fmt: off
from custom_components.hh_modbus_control.data.enums import DataType  # noqa: E402
from custom_components.hh_modbus_control.sensor_data.givenergy_sensors import (  # noqa: E402
    givenergy_holding_sensors,
    givenergy_input_sensors,
)
from custom_components.hh_modbus_control.sensor_data.hybrid_sensors import hybrid_sensors  # noqa: E402
from custom_components.hh_modbus_control.sensor_data.sigenergy_sensors import sigenergy_plant_sensors  # noqa: E402
from custom_components.hh_modbus_control.sensor_data.skyline_sensors import (  # noqa: E402
    skyline_battery_sensors,
    skyline_dcdc_version_sensors,
    skyline_grid_sensors,
    skyline_identity_sensors,
    skyline_inverter_power_sensors,
    skyline_version_sensors,
)
from custom_components.hh_modbus_control.sensor_data.solaredge_sensors import (  # noqa: E402
    solaredge_info_sensors,
    solaredge_inverter_sensors,
)
from custom_components.hh_modbus_control.sensor_data.string_sensors import string_sensors  # noqa: E402
from custom_components.hh_modbus_control.sensor_data.sunsynk_single_phase import (  # noqa: E402
    sunsynk_holding_sensors,
    sunsynk_input_sensors,
)
# fmt: on

# ---------------------------------------------------------------------------
# Pymodbus server imports
# ---------------------------------------------------------------------------
try:
    # pymodbus 3.7+ preferred API
    from pymodbus.simulator import SimDevice
    from pymodbus.simulator.simdata import DataType as SimDataType, SimData
    _USE_SIMDEVICE = True
except ImportError:
    _USE_SIMDEVICE = False

if not _USE_SIMDEVICE:
    # Older pymodbus 3.x fallback (deprecated in 3.13)
    from pymodbus.datastore import (  # type: ignore[assignment]
        ModbusDeviceContext,
        ModbusSequentialDataBlock,
        ModbusServerContext,
    )

from pymodbus.server import StartAsyncTcpServer  # noqa: E402

_LOGGER = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Brand → sensor group mapping
# Each entry is {"holding": [...groups...], "input": [...groups...]}
# ---------------------------------------------------------------------------
BRAND_SENSOR_GROUPS: dict[str, dict[str, list]] = {
    "solis": {
        "holding": hybrid_sensors + string_sensors,
        "input": [],
    },
    "sunsynk": {
        "holding": sunsynk_holding_sensors,
        "input": sunsynk_input_sensors,
    },
    "deye": {
        "holding": sunsynk_holding_sensors,
        "input": sunsynk_input_sensors,
    },
    "givenergy": {
        "holding": givenergy_holding_sensors,
        "input": givenergy_input_sensors,
    },
    "sigenergy": {
        "holding": sigenergy_plant_sensors,
        "input": [],
    },
    "solaredge": {
        "holding": solaredge_info_sensors + solaredge_inverter_sensors,
        "input": [],
    },
    "skyline": {
        "holding": (
            skyline_identity_sensors
            + skyline_version_sensors
            + skyline_dcdc_version_sensors
            + skyline_inverter_power_sensors
            + skyline_grid_sensors
            + skyline_battery_sensors
        ),
        "input": [],
    },
    "duracell": {
        # Duracell G3 is a rebranded Skyline without the DCDC version register
        "holding": (
            skyline_identity_sensors
            + skyline_version_sensors
            + skyline_inverter_power_sensors
            + skyline_grid_sensors
            + skyline_battery_sensors
        ),
        "input": [],
    },
}

# Default Modbus TCP port per brand
BRAND_DEFAULT_PORTS: dict[str, int] = {
    "solis": 502,
    "sunsynk": 502,
    "deye": 502,
    "givenergy": 8899,
    "sigenergy": 502,
    "solaredge": 1502,
    "skyline": 502,
    "duracell": 502,
}

# ---------------------------------------------------------------------------
# Realistic default value calculation
# ---------------------------------------------------------------------------

_UNIT_TARGET_VALUES: dict[str, float] = {
    "v": 230.0,       # Voltage (V) — grid voltage
    "a": 10.0,        # Current (A)
    "w": 3000.0,      # Power (W)
    "kw": 3.0,        # Power (kW)
    "kwh": 500.0,     # Energy (kWh) — fits in a single U16 register with ×0.1 multiplier
    "wh": 500_000.0,  # Energy (Wh) — fits in a single U16 register with ×0.01 multiplier
    "hz": 50.0,       # Frequency (Hz)
    "°c": 25.0,       # Temperature (°C)
    "%": 75.0,        # Percentage (e.g. battery SOC)
    "va": 3000.0,     # Apparent power (VA)
    "var": 100.0,     # Reactive power (var)
    "s": 12.0,        # Time (seconds)
    "min": 12.0,      # Time (minutes)
    "h": 12.0,        # Time (hours)
    "kvah": 500.0,    # Apparent energy
    "kvarh": 100.0,   # Reactive energy
}

_DEVICE_CLASS_TARGET_VALUES: dict[str, float] = {
    "voltage": 230.0,
    "current": 10.0,
    "power": 3000.0,
    "energy": 500.0,    # conservative — fits in a single U16 register with ×0.1 multiplier
    "frequency": 50.0,
    "temperature": 25.0,
    "battery": 75.0,
    "apparent_power": 3000.0,
    "reactive_power": 100.0,
    "duration": 12.0,
}


def _target_value(entity: dict) -> float:
    """Return a realistic display value for a sensor based on its metadata."""
    unit = str(entity.get("unit_of_measurement", "")).lower().strip()
    device_class = str(entity.get("device_class", "")).lower()
    name = entity.get("name", "").lower()

    # Unit-based lookup (most specific)
    if unit in _UNIT_TARGET_VALUES:
        val = _UNIT_TARGET_VALUES[unit]
        # Adjust voltage for DC / battery contexts
        if unit == "v":
            if "battery" in name or "batt" in name:
                return 52.0
            if any(k in name for k in ("pv", "dc", "string")):
                return 380.0
        return val

    # Device-class fallback
    if device_class in _DEVICE_CLASS_TARGET_VALUES:
        return _DEVICE_CLASS_TARGET_VALUES[device_class]

    return 10.0


def _encode_string(text: str, count: int) -> list[int]:
    """Encode ASCII text into Modbus register values (2 chars per register)."""
    padded = text.ljust(count * 2, "\x00")[: count * 2]
    return [(ord(padded[i]) << 8) | ord(padded[i + 1]) for i in range(0, count * 2, 2)]


def _entity_default_values(entity: dict) -> list[int]:
    """Return raw Modbus register values for a sensor entity."""
    registers = entity.get("register", [])
    count = len(registers)
    if count == 0:
        return []

    multiplier = entity.get("multiplier", 0)
    data_type = entity.get("data_type")

    # Hidden / reserve registers — leave at zero
    if entity.get("hidden") or entity.get("type") == "reserve":
        return [0] * count

    # String data type
    if data_type == DataType.STRING:
        return _encode_string("SIMULATOR", count)

    # Multiplier = 0 means the raw value is displayed directly (version, status, model, etc.)
    if multiplier == 0:
        if count >= 4:
            # Multi-register with no scaling is likely a string field
            return _encode_string("SIMULATOR-HH", count)
        return [1] * count

    # Compute raw register value from the realistic display value
    target = _target_value(entity)
    abs_mult = abs(multiplier)
    raw = round(target / abs_mult)

    # Signed 16-bit
    if data_type == DataType.S16 or (multiplier < 0 and count == 1):
        raw = max(-32768, min(32767, raw))
        return [raw & 0xFFFF]

    # Signed 32-bit (2 registers, high word first)
    if data_type == DataType.S32:
        raw = max(-2_147_483_648, min(2_147_483_647, raw))
        return [(raw >> 16) & 0xFFFF, raw & 0xFFFF]

    # Unsigned 32-bit (2 registers, high word first)
    if data_type == DataType.U32 or count == 2:
        raw = max(0, min(4_294_967_295, raw))
        return [(raw >> 16) & 0xFFFF, raw & 0xFFFF]

    # Default: unsigned 16-bit
    raw = max(0, min(65535, raw))
    return [raw]


def build_register_map(sensor_groups: list[dict]) -> dict[int, int]:
    """Build a {register_address: raw_value} mapping from sensor group definitions."""
    reg_map: dict[int, int] = {}
    for group in sensor_groups:
        for entity in group.get("entities", []):
            registers = entity.get("register", [])
            values = _entity_default_values(entity)
            for addr_str, val in zip(registers, values):
                reg_map[int(addr_str)] = val
    return reg_map


# ---------------------------------------------------------------------------
# Pymodbus data-block builders (two implementations: new SimData or legacy)
# ---------------------------------------------------------------------------

def _u16_to_signed(v: int) -> int:
    """Convert an unsigned 16-bit integer to its two's-complement signed equivalent.

    SimData with DataType.REGISTERS packs each value as a signed int16 (struct 'h'),
    so unsigned values > 32767 must be represented as negative numbers.
    """
    v = v & 0xFFFF
    return v - 65536 if v > 32767 else v


def _build_simdata_blocks(reg_map: dict[int, int]) -> list:
    """Convert {addr: value} to a list of contiguous SimData REGISTERS blocks."""
    if not reg_map:
        return []

    sorted_addrs = sorted(reg_map)
    blocks = []
    i = 0
    while i < len(sorted_addrs):
        start = sorted_addrs[i]
        values = [_u16_to_signed(reg_map[start])]
        j = i + 1
        # Extend the block as long as addresses are contiguous
        while j < len(sorted_addrs) and sorted_addrs[j] == start + len(values):
            values.append(_u16_to_signed(reg_map[sorted_addrs[j]]))
            j += 1
        blocks.append(
            SimData(address=start, count=1, values=values, datatype=SimDataType.REGISTERS)
        )
        i = j
    return blocks


def _build_legacy_block(reg_map: dict[int, int]):
    """Build a ModbusSequentialDataBlock covering the full address range."""
    if not reg_map:
        return ModbusSequentialDataBlock(1, [0])
    lo = min(reg_map)
    hi = max(reg_map)
    block = [0] * (hi - lo + 1)
    for addr, val in reg_map.items():
        block[addr - lo] = val
    return ModbusSequentialDataBlock(lo, block)


# ---------------------------------------------------------------------------
# Server context builders
# ---------------------------------------------------------------------------

_BITS_PLACEHOLDER = None  # lazy-initialised


def _bits_placeholder():
    global _BITS_PLACEHOLDER
    if _BITS_PLACEHOLDER is None:
        _BITS_PLACEHOLDER = SimData(address=1, count=1, values=0, datatype=SimDataType.BITS)
    return _BITS_PLACEHOLDER


def build_server_context(holding_map: dict[int, int], input_map: dict[int, int], slave: int):
    """Return a pymodbus server context populated with the given register maps."""
    if _USE_SIMDEVICE:
        hr_blocks = _build_simdata_blocks(holding_map) or [
            SimData(address=1, count=1, values=0, datatype=SimDataType.REGISTERS)
        ]
        ir_blocks = _build_simdata_blocks(input_map) or [
            SimData(address=1, count=1, values=0, datatype=SimDataType.REGISTERS)
        ]
        co = [_bits_placeholder()]
        di = [_bits_placeholder()]
        # Tuple order: (coils, discrete_inputs, holding_registers, input_registers)
        device = SimDevice(id=slave, simdata=(co, di, hr_blocks, ir_blocks))
        return device

    # Legacy path (pymodbus < 3.7 or SimDevice unavailable)
    store = ModbusDeviceContext(
        di=ModbusSequentialDataBlock(1, [0]),
        co=ModbusSequentialDataBlock(1, [0]),
        hr=_build_legacy_block(holding_map),
        ir=_build_legacy_block(input_map),
    )
    return ModbusServerContext(devices={slave: store}, single=False)


# ---------------------------------------------------------------------------
# Main simulator coroutine
# ---------------------------------------------------------------------------

async def run_simulator(brand: str, host: str, port: int, slave: int, verbose: bool) -> None:
    """Build the register maps and start the Modbus TCP server."""
    groups = BRAND_SENSOR_GROUPS[brand]
    holding_map = build_register_map(groups["holding"])
    input_map = build_register_map(groups["input"])

    _LOGGER.info("Brand '%s' — holding registers: %d, input registers: %d",
                 brand, len(holding_map), len(input_map))

    if verbose:
        if holding_map:
            print("\nHolding registers:")
            for addr in sorted(holding_map):
                print(f"  HR[{addr:5d}] = {holding_map[addr]}")
        if input_map:
            print("\nInput registers:")
            for addr in sorted(input_map):
                print(f"  IR[{addr:5d}] = {input_map[addr]}")

    context = build_server_context(holding_map, input_map, slave)

    print(f"\n🔌  Modbus TCP simulator ready")
    print(f"    Brand  : {brand}")
    print(f"    Address: {host}:{port}  (slave={slave})")
    print(f"    HR populated: {len(holding_map)} registers")
    if input_map:
        print(f"    IR populated: {len(input_map)} registers")
    print("\n    Point the hh_modbus_control integration at this host/port.")
    print("    Press Ctrl+C to stop.\n")

    await StartAsyncTcpServer(context, address=(host, port))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Inverter Modbus TCP simulator for hh_modbus_control",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--brand",
        required=True,
        choices=sorted(BRAND_SENSOR_GROUPS.keys()),
        metavar="BRAND",
        help=f"Inverter brand to simulate. Choices: {', '.join(sorted(BRAND_SENSOR_GROUPS.keys()))}",
    )
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="IP address to listen on (default: 0.0.0.0 = all interfaces)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Modbus TCP port to listen on (default: brand-specific, e.g. 8899 for GivEnergy)",
    )
    parser.add_argument(
        "--slave",
        type=int,
        default=1,
        help="Modbus slave / device ID to answer on (default: 1)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print all populated register addresses and values on startup",
    )
    parser.add_argument(
        "--log-level",
        default="WARNING",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level (default: WARNING)",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=args.log_level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    port = args.port if args.port is not None else BRAND_DEFAULT_PORTS[args.brand]

    try:
        asyncio.run(run_simulator(args.brand, args.host, port, args.slave, args.verbose))
    except KeyboardInterrupt:
        print("\nSimulator stopped.")


if __name__ == "__main__":
    main()
