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

Enable the Web UI to interactively change register values in your browser:
    python simulator/inverter_simulator.py --brand solis --port 5020 --web-ui-port 8080
    Then open http://localhost:8080 in your browser.

Supported brands:
    solis, sunsynk, deye, givenergy, sigenergy, solaredge, skyline, duracell
"""


import argparse
import asyncio
import json
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

    # ModbusTcpServer lets us keep a reference to the internal SimCore context
    # so that the Web UI can push live register updates via async_setValues.
    try:
        from pymodbus.server import ModbusTcpServer as _ModbusTcpServer
        _HAS_MODBUS_TCP_SERVER = True
    except ImportError:
        _HAS_MODBUS_TCP_SERVER = False

    from pymodbus.server import StartAsyncTcpServer  # noqa: E402
except ModuleNotFoundError as exc:
    if exc.name == "pymodbus":
        raise SystemExit(
            "Missing dependency: 'pymodbus'.\n"
            "Install project dependencies first:\n"
            "  uv sync\n"
            "Then run the simulator via uv:\n"
            "  uv run python simulator/inverter_simulator.py --brand solis --port 5020\n"
            "(Use a port >1024 to avoid sudo.)"
        ) from exc
    raise

_LOGGER = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional aiohttp import for the Web UI
# ---------------------------------------------------------------------------
try:
    from aiohttp import web as _aiohttp_web
    _HAS_AIOHTTP = True
except ImportError:
    _HAS_AIOHTTP = False

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


def build_sensor_info_and_map(
    sensor_groups: list[dict], register_type: str = "holding"
) -> tuple[dict[int, int], list[dict]]:
    """Build register map and sensor metadata list from sensor group definitions.

    Returns:
        reg_map: {register_address: raw_value}
        sensor_info: list of sensor metadata dicts (used by the Web UI)
    """
    reg_map: dict[int, int] = {}
    sensor_info: list[dict] = []

    for group in sensor_groups:
        group_name = group.get("name", "Other")
        for entity in group.get("entities", []):
            registers = entity.get("register", [])
            if not registers:
                continue
            values = _entity_default_values(entity)
            multiplier = entity.get("multiplier", 0)
            data_type = entity.get("data_type")
            is_hidden = bool(entity.get("hidden") or entity.get("type") == "reserve")
            is_string = _is_data_type(data_type, "STRING")

            # Normalise data_type to the string name (e.g. "S16") regardless of
            # whether the sensor file stores it as a DataType enum or a raw string.
            if data_type is None:
                dt_name: str | None = None
            elif isinstance(data_type, str):
                dt_name = data_type
            else:
                dt_name = data_type.name

            for addr_str, val in zip(registers, values):
                reg_map[int(addr_str)] = val

            display_val = _compute_display_value(
                values, multiplier, data_type, len(registers)
            )

            sensor_info.append({
                "name": entity.get("name", ""),
                "group": group_name,
                "registers": [int(r) for r in registers],
                "register_type": register_type,
                "unit": entity.get("unit_of_measurement", ""),
                "multiplier": multiplier,
                "data_type": dt_name,
                "display_value": display_val,
                "hidden": is_hidden,
                "is_string": is_string,
            })

    return reg_map, sensor_info


def _is_data_type(value: "DataType | str | None", name: str) -> bool:
    """Return True if *value* represents the DataType identified by *name*.

    Handles both enum instances (``DataType.S16``) and raw strings (``"S16"``).
    """
    if value is None:
        return False
    if isinstance(value, str):
        return value == name
    return value.name == name


def _compute_display_value(
    raw_values: list[int],
    multiplier: float,
    data_type: "DataType | None",
    count: int,
) -> float | int:
    """Convert raw Modbus register value(s) to a human-readable display value.

    Args:
        raw_values: List of raw unsigned-16-bit register words (high word first
                    for 32-bit sensors).
        multiplier: The sensor's scaling multiplier.  A value of 0 means the raw
                    register is returned unchanged.  A negative multiplier implies
                    the raw value is signed.
        data_type:  The :class:`DataType` enum member for this sensor, or *None*.
        count:      Number of registers the sensor occupies (1 or 2).

    Returns:
        The scaled display value as a *float* (or *int* when multiplier is 0).
    """
    if not raw_values:
        return 0
    if multiplier == 0:
        return raw_values[0]

    if count >= 2 and len(raw_values) >= 2:
        raw = (raw_values[0] << 16) | raw_values[1]
        if _is_data_type(data_type, "S32") and raw > 0x7FFF_FFFF:
            raw -= 0x1_0000_0000
    else:
        raw = raw_values[0]
        if _is_data_type(data_type, "S16") and raw > 32767:
            raw -= 65536
        elif multiplier < 0 and raw > 32767:
            raw -= 65536

    return raw * abs(multiplier)


def _display_to_raw_values(
    display_value: float,
    multiplier: float,
    data_type_name: str | None,
    count: int,
) -> list[int]:
    """Convert a human-readable display value back to raw Modbus register word(s).

    Args:
        display_value:  The value as shown in the UI (already scaled by multiplier).
        multiplier:     The sensor's scaling multiplier.  0 means pass-through (no
                        scaling); the raw value is clamped to unsigned 16-bit range.
        data_type_name: String name of the :class:`DataType` (e.g. ``"S16"``,
                        ``"U32"``), or *None* to default to unsigned 16-bit.
        count:          Number of registers the sensor occupies (1 or 2).

    Returns:
        A list of ``count`` unsigned 16-bit integers (high word first for 32-bit
        sensors) ready to be written to the Modbus datastore.
    """
    if multiplier == 0:
        v = max(0, min(65535, round(float(display_value))))
        return [v] * count

    abs_mult = abs(multiplier)
    raw = round(float(display_value) / abs_mult)

    if count >= 2:
        if data_type_name == "S32":
            raw = max(-2_147_483_648, min(2_147_483_647, raw))
        else:
            raw = max(0, min(4_294_967_295, raw))
        return [(raw >> 16) & 0xFFFF, raw & 0xFFFF]

    if data_type_name == "S16" or (multiplier < 0 and count == 1):
        raw = max(-32768, min(32767, raw))
        return [raw & 0xFFFF]

    raw = max(0, min(65535, raw))
    return [raw]


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
    """Build a ModbusSequentialDataBlock covering the full address range.

    Values are sign-converted to the two's-complement range expected by
    pymodbus (which stores registers as signed int16 internally).
    """
    if not reg_map:
        return ModbusSequentialDataBlock(1, [0])
    lo = min(reg_map)
    hi = max(reg_map)
    block = [0] * (hi - lo + 1)
    for addr, val in reg_map.items():
        block[addr - lo] = _u16_to_signed(val)
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
    """Return a pymodbus server context (SimDevice or legacy) populated with the given register maps."""
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
# Web UI — HTML template (served at GET /)
# ---------------------------------------------------------------------------

_WEB_UI_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>HH Modbus Simulator</title>
<style>
:root{--primary:#2563eb;--primary-dark:#1d4ed8;--bg:#f1f5f9;--card:#fff;--border:#e2e8f0;--text:#1e293b;--muted:#64748b;--ok:#16a34a;--err:#dc2626}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;background:var(--bg);color:var(--text);padding:1rem}
header{background:var(--primary);color:#fff;padding:.75rem 1.25rem;border-radius:.5rem;margin-bottom:1rem;display:flex;align-items:center;gap:.75rem;flex-wrap:wrap}
header h1{font-size:1.1rem;font-weight:600;flex:1}
.badge{background:rgba(255,255,255,.2);padding:.2rem .7rem;border-radius:999px;font-size:.8rem;white-space:nowrap}
.dot{width:8px;height:8px;border-radius:50%;background:#4ade80;flex-shrink:0;animation:pulse 2s infinite}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.4}}
.toolbar{display:flex;gap:.75rem;margin-bottom:1rem;flex-wrap:wrap;align-items:center}
.search{flex:1;min-width:160px;padding:.45rem .85rem;border:1px solid var(--border);border-radius:.375rem;font-size:.875rem;background:var(--card)}
.search:focus{outline:none;border-color:var(--primary)}
.toggle{display:flex;align-items:center;gap:.4rem;font-size:.8rem;color:var(--muted);cursor:pointer;user-select:none;white-space:nowrap}
.group{background:var(--card);border:1px solid var(--border);border-radius:.5rem;margin-bottom:.75rem;overflow:hidden}
.group-hdr{padding:.6rem 1rem;background:#f8fafc;font-weight:600;font-size:.8rem;cursor:pointer;display:flex;justify-content:space-between;align-items:center;user-select:none;border-bottom:1px solid var(--border)}
.group-hdr:hover{background:#f1f5f9}
.group-hdr .cnt{font-weight:400;color:var(--muted)}
.group-body{overflow-x:auto}
table{width:100%;border-collapse:collapse;font-size:.82rem}
thead th{padding:.4rem .7rem;text-align:left;font-size:.7rem;font-weight:700;text-transform:uppercase;color:var(--muted);letter-spacing:.05em;background:#fafafa;border-bottom:1px solid var(--border)}
tbody tr:hover{background:#f8fafc}
tbody tr:not(:last-child) td{border-bottom:1px solid #f1f5f9}
td{padding:.35rem .7rem;vertical-align:middle}
.mono{font-family:monospace;color:var(--muted);font-size:.75rem}
.name{font-weight:500}
.unit{color:var(--muted);font-size:.75rem}
.val-wrap{display:flex;align-items:center;gap:.3rem}
input.val{width:110px;padding:.25rem .5rem;border:1px solid var(--border);border-radius:.25rem;font-size:.82rem;text-align:right;transition:border-color .15s}
input.val:focus{outline:none;border-color:var(--primary)}
input.val.ok{border-color:var(--ok)}
input.val.err{border-color:var(--err)}
.type-tag{font-size:.65rem;background:#f1f5f9;color:var(--muted);border-radius:.2rem;padding:.1rem .3rem}
.toast{position:fixed;bottom:1.25rem;right:1.25rem;padding:.6rem 1rem;border-radius:.375rem;color:#fff;font-size:.82rem;opacity:0;transition:opacity .2s;pointer-events:none;z-index:999}
.toast.ok-bg{background:var(--ok)}
.toast.err-bg{background:var(--err)}
.toast.show{opacity:1}
</style>
</head>
<body>
<header>
  <span class="dot"></span>
  <h1>HH Modbus Inverter Simulator</h1>
  <span class="badge" id="brand-badge">Loading…</span>
  <span class="badge" id="addr-badge"></span>
</header>
<div class="toolbar">
  <input class="search" id="search" type="search" placeholder="Filter by sensor name…">
  <label class="toggle"><input type="checkbox" id="show-hidden"> Show hidden / reserve registers</label>
</div>
<div id="container"></div>
<div class="toast" id="toast"></div>
<script>
let sensors=[], info={}, debounce={};

async function init(){
  const r=await fetch('/api/info');
  info=await r.json();
  document.getElementById('brand-badge').textContent=info.brand.toUpperCase();
  document.getElementById('addr-badge').textContent=info.modbus_address;
  document.title='HH Modbus Simulator – '+info.brand;
  await refresh();
}

async function refresh(){
  const r=await fetch('/api/sensors');
  sensors=await r.json();
  render();
}

function render(){
  const q=document.getElementById('search').value.toLowerCase();
  const showHidden=document.getElementById('show-hidden').checked;
  const vis=sensors.filter(s=>{
    if(!showHidden&&s.hidden) return false;
    if(q&&!s.name.toLowerCase().includes(q)) return false;
    return true;
  });
  const groups={};
  for(const s of vis)(groups[s.group]||(groups[s.group]=[])).push(s);
  const c=document.getElementById('container');
  c.innerHTML='';
  for(const[g,list] of Object.entries(groups)) c.appendChild(mkGroup(g,list));
}

function mkGroup(name,list){
  const sec=document.createElement('div'); sec.className='group';
  const hdr=document.createElement('div'); hdr.className='group-hdr';
  hdr.innerHTML='<span>'+esc(name)+'</span><span class="cnt">'+list.length+' sensors</span>';
  const body=document.createElement('div'); body.className='group-body';
  const tbl=document.createElement('table');
  tbl.innerHTML='<thead><tr><th>Register</th><th>Sensor Name</th><th>Value</th><th>Unit</th><th>Type</th></tr></thead>';
  const tb=document.createElement('tbody');
  for(const s of list) tb.appendChild(mkRow(s));
  tbl.appendChild(tb); body.appendChild(tbl);
  hdr.onclick=()=>{ body.style.display=body.style.display==='none'?'':'none'; };
  sec.appendChild(hdr); sec.appendChild(body);
  return sec;
}

function mkRow(s){
  const tr=document.createElement('tr');
  const reg=s.registers[0], rt=s.register_type;
  const prefix=rt==='holding'?'HR':'IR';
  const step=s.multiplier!==0?Math.abs(s.multiplier):1;
  tr.innerHTML=
    '<td class="mono">'+prefix+'['+reg+']</td>'+
    '<td class="name">'+esc(s.name||'—')+'</td>'+
    '<td><div class="val-wrap">'+
      (s.is_string
        ? '<span class="mono">'+esc(String(s.display_value))+'</span>'
        : '<input class="val" type="number" data-reg="'+reg+'" data-rt="'+rt+'" value="'+fmt(s.display_value)+'" step="'+step+'">'
      )+
    '</div></td>'+
    '<td class="unit">'+esc(s.unit||'')+'</td>'+
    '<td><span class="type-tag">'+esc(s.data_type||'U16')+'</span></td>';
  if(!s.is_string){
    const inp=tr.querySelector('input.val');
    inp.addEventListener('change', e=>doUpdate(e.target));
    inp.addEventListener('input', e=>{
      clearTimeout(debounce[reg]);
      debounce[reg]=setTimeout(()=>doUpdate(e.target),900);
    });
  }
  return tr;
}

async function doUpdate(inp){
  const reg=parseInt(inp.dataset.reg), rt=inp.dataset.rt;
  const val=parseFloat(inp.value);
  if(isNaN(val)) return;
  clearTimeout(debounce[reg]);
  try{
    const r=await fetch('/api/update',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({register:reg,register_type:rt,display_value:val})});
    if(r.ok){
      const s=sensors.find(x=>x.registers[0]===reg); if(s) s.display_value=val;
      inp.classList.remove('err'); inp.classList.add('ok');
      setTimeout(()=>inp.classList.remove('ok'),1200);
      toast('Updated '+reg,'ok-bg');
    } else {
      inp.classList.add('err'); toast('Update failed','err-bg');
    }
  }catch(e){ inp.classList.add('err'); toast('Error: '+e.message,'err-bg'); }
}

let toastT;
function toast(msg,cls){
  const el=document.getElementById('toast');
  el.textContent=msg; el.className='toast '+cls+' show';
  clearTimeout(toastT); toastT=setTimeout(()=>el.classList.remove('show'),2200);
}

function fmt(v){
  if(v===null||v===undefined) return 0;
  const n=parseFloat(v); if(isNaN(n)) return v;
  return parseFloat(n.toFixed(4));
}

function esc(s){ const d=document.createElement('div'); d.textContent=s; return d.innerHTML; }

document.getElementById('search').addEventListener('input',render);
document.getElementById('show-hidden').addEventListener('change',render);

init();
</script>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Web UI — aiohttp request handlers
# ---------------------------------------------------------------------------

def _make_web_app(
    brand: str,
    modbus_address: str,
    holding_map: dict[int, int],
    input_map: dict[int, int],
    sensor_info: list[dict],
    sim_core: "object | None",
    slave: int,
) -> "_aiohttp_web.Application":
    """Create and return the aiohttp Application for the Web UI."""
    app = _aiohttp_web.Application()
    app["brand"] = brand
    app["modbus_address"] = modbus_address
    app["holding_map"] = holding_map
    app["input_map"] = input_map
    app["sensor_info"] = sensor_info
    app["sim_core"] = sim_core
    app["slave"] = slave

    app.router.add_get("/", _handle_index)
    app.router.add_get("/api/info", _handle_info)
    app.router.add_get("/api/sensors", _handle_sensors)
    app.router.add_post("/api/update", _handle_update)
    return app


async def _handle_index(request: "_aiohttp_web.Request") -> "_aiohttp_web.Response":
    return _aiohttp_web.Response(text=_WEB_UI_HTML, content_type="text/html")


async def _handle_info(request: "_aiohttp_web.Request") -> "_aiohttp_web.Response":
    return _aiohttp_web.Response(
        text=json.dumps({
            "brand": request.app["brand"],
            "modbus_address": request.app["modbus_address"],
        }),
        content_type="application/json",
    )


async def _handle_sensors(request: "_aiohttp_web.Request") -> "_aiohttp_web.Response":
    """Return sensor list with current display values computed from live register maps."""
    holding_map: dict[int, int] = request.app["holding_map"]
    input_map: dict[int, int] = request.app["input_map"]
    sensor_info: list[dict] = request.app["sensor_info"]

    result = []
    for s in sensor_info:
        reg_map = holding_map if s["register_type"] == "holding" else input_map
        raw_vals = [reg_map.get(r, 0) for r in s["registers"]]

        # Reconstruct DataType for display-value computation
        dt_name = s["data_type"]
        try:
            data_type = DataType[dt_name] if dt_name else None
        except KeyError:
            data_type = None

        display = _compute_display_value(raw_vals, s["multiplier"], data_type, len(s["registers"]))

        entry = dict(s)
        entry["display_value"] = display
        entry["raw_values"] = raw_vals
        result.append(entry)

    return _aiohttp_web.Response(
        text=json.dumps(result),
        content_type="application/json",
    )


async def _handle_update(request: "_aiohttp_web.Request") -> "_aiohttp_web.Response":
    """Accept a display-value update and propagate it to the live Modbus datastore."""
    try:
        data = await request.json()
        register: int = int(data["register"])
        display_value: float = float(data["display_value"])
        register_type: str = str(data.get("register_type", "holding"))
    except (KeyError, ValueError, TypeError):
        return _aiohttp_web.Response(
            text=json.dumps({"error": "Invalid request: 'register', 'display_value' and optionally 'register_type' are required."}),
            status=400,
            content_type="application/json",
        )

    sensor_info: list[dict] = request.app["sensor_info"]
    holding_map: dict[int, int] = request.app["holding_map"]
    input_map: dict[int, int] = request.app["input_map"]
    sim_core = request.app["sim_core"]
    slave: int = request.app["slave"]

    sensor = next(
        (s for s in sensor_info if s["registers"][0] == register and s["register_type"] == register_type),
        None,
    )
    if sensor is None:
        return _aiohttp_web.Response(
            text=json.dumps({"error": "Sensor not found"}),
            status=404,
            content_type="application/json",
        )

    raw_vals = _display_to_raw_values(
        display_value,
        sensor["multiplier"],
        sensor["data_type"],
        len(sensor["registers"]),
    )

    reg_map = holding_map if register_type == "holding" else input_map
    fc = 3 if register_type == "holding" else 4

    for addr, val in zip(sensor["registers"], raw_vals):
        reg_map[addr] = val
        try:
            signed_val = _u16_to_signed(val)
            if sim_core is not None and hasattr(sim_core, "async_setValues"):
                await sim_core.async_setValues(slave, fc, addr, [signed_val])
        except Exception:
            _LOGGER.warning("Could not update register %d in live context", addr)

    return _aiohttp_web.Response(
        text=json.dumps({"ok": True, "raw_values": raw_vals}),
        content_type="application/json",
    )


# ---------------------------------------------------------------------------
# Main simulator coroutine
# ---------------------------------------------------------------------------

async def run_simulator(
    brand: str,
    host: str,
    port: int,
    slave: int,
    verbose: bool,
    web_ui_port: int | None = None,
) -> None:
    """Build the register maps and start the Modbus TCP server (and optional Web UI)."""
    groups = BRAND_SENSOR_GROUPS[brand]

    # Use the richer builder when the Web UI is requested so we get sensor metadata.
    if web_ui_port is not None:
        holding_map, holding_info = build_sensor_info_and_map(groups["holding"], "holding")
        input_map, input_info = build_sensor_info_and_map(groups["input"], "input")
        sensor_info = holding_info + input_info
    else:
        holding_map = build_register_map(groups["holding"])
        input_map = build_register_map(groups["input"])
        sensor_info = []

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

    # When the Web UI is active, use ModbusTcpServer directly so we can keep
    # a reference to the SimCore context for async live register updates.
    context = build_server_context(holding_map, input_map, slave)

    print(f"\n🔌  Modbus TCP simulator ready")
    print(f"    Brand  : {brand}")
    print(f"    Address: {host}:{port}  (slave={slave})")
    print(f"    HR populated: {len(holding_map)} registers")
    if input_map:
        print(f"    IR populated: {len(input_map)} registers")

    if web_ui_port is not None:
        if not _HAS_AIOHTTP:
            raise SystemExit(
                "aiohttp is required for the Web UI.\n"
                "Install it with:  pip install aiohttp\n"
                "or:               uv add aiohttp"
            )

        # Build the TCP server early to get a reference to SimCore.
        if _HAS_MODBUS_TCP_SERVER:
            tcp_server = _ModbusTcpServer(context, address=(host, port))
            sim_core = tcp_server.context  # SimCore with async_setValues
        else:
            tcp_server = None
            sim_core = None

        web_app = _make_web_app(
            brand=brand,
            modbus_address=f"{host}:{port}",
            holding_map=holding_map,
            input_map=input_map,
            sensor_info=sensor_info,
            sim_core=sim_core,
            slave=slave,
        )
        runner = _aiohttp_web.AppRunner(web_app)
        await runner.setup()
        site = _aiohttp_web.TCPSite(runner, "0.0.0.0", web_ui_port)
        await site.start()
        print(f"    Web UI : http://0.0.0.0:{web_ui_port}")
        _LOGGER.warning(
            "Web UI bound to 0.0.0.0:%d — accessible from all network interfaces. "
            "Restrict access via firewall rules in untrusted networks.",
            web_ui_port,
        )

    print("\n    Point the hh_modbus_control integration at this host/port.")
    print("    Press Ctrl+C to stop.\n")

    if web_ui_port is not None and tcp_server is not None:
        await tcp_server.serve_forever()
    else:
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
    parser.add_argument(
        "--web-ui-port",
        type=int,
        default=None,
        metavar="PORT",
        help=(
            "Enable the Web UI on this port (e.g. 8080). "
            "Open http://localhost:<PORT> in your browser to view and edit simulated register values. "
            "The Web UI binds to 0.0.0.0 (all interfaces) — restrict access via firewall in untrusted networks. "
            "Requires aiohttp (pip install aiohttp). Disabled by default."
        ),
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=args.log_level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    port = args.port if args.port is not None else BRAND_DEFAULT_PORTS[args.brand]

    try:
        asyncio.run(
            run_simulator(
                args.brand,
                args.host,
                port,
                args.slave,
                args.verbose,
                web_ui_port=args.web_ui_port,
            )
        )
    except KeyboardInterrupt:
        print("\nSimulator stopped.")


if __name__ == "__main__":
    main()
