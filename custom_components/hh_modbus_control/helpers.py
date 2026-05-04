import logging
import struct
from datetime import datetime

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.util import dt as dt_utils

from custom_components.hh_modbus_control.const import (
    CONN_TYPE_TCP,
    CONTROLLER,
    DOMAIN,
    DRIFT_COUNTER,
    NUMBER_ENTITIES,
    REGISTER,
    SENSOR_ENTITIES,
    SLAVE,
    VALUE,
    VALUES,
)

_LOGGER = logging.getLogger(__name__)


def hex_to_ascii(hex_value):
    decimal_value = hex_value
    byte1 = (decimal_value >> 8) & 0xFF
    byte2 = decimal_value & 0xFF
    return "".join([chr(byte) for byte in [byte1, byte2]])


def unique_id_generator(controller, third_value, fourth_value=None):
    if fourth_value is None:
        if controller.device_serial_number is not None:
            return f"{DOMAIN}_{controller.device_serial_number}_{third_value}"
        if controller.identification is not None:
            return f"{DOMAIN}_{controller.identification}_{third_value}"
        return f"{DOMAIN}_{controller.host}_{third_value}"
    else:
        if controller.device_serial_number is not None:
            return f"{DOMAIN}_{controller.device_serial_number}_{third_value}_{fourth_value}"
        if controller.identification is not None:
            return f"{DOMAIN}_{controller.identification}_{third_value}_{fourth_value}"
        return f"{DOMAIN}_{controller.host}_{third_value}_{fourth_value}"


def unique_id_generator_binary(controller, register, bit_position, on_value):
    if controller.device_serial_number is not None:
        return f"{DOMAIN}_{controller.device_serial_number}_{register}_{on_value if on_value is not None else bit_position}"
    if controller.identification is not None:
        return f"{DOMAIN}_{controller.identification}_{register}_{on_value if on_value is not None else bit_position}"
    return f"{DOMAIN}_{controller.host}_{register}_{on_value if on_value is not None else bit_position}"


def extract_serial_number(values):
    packed = struct.pack(">" + "H" * len(values), *values)
    return packed.decode("ascii", errors="ignore").strip("\x00\r\n ")


def clock_drift_test(hass, controller, hours, minutes, seconds):
    current_time = dt_utils.now()
    device_time = datetime(current_time.year, current_time.month, current_time.day, hours, minutes, seconds, tzinfo=current_time.tzinfo)
    total_drift = (current_time - device_time).total_seconds()

    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}
    drift_counter = hass.data[DOMAIN].get(DRIFT_COUNTER, 0)
    clock_adjusted = False

    if abs(total_drift) > 60:
        if drift_counter > 5:
            if controller.connected():
                hass.create_task(controller.async_write_holding_registers(43003, [current_time.hour, current_time.minute, current_time.second]))
                clock_adjusted = True
        else:
            hass.data[DOMAIN][DRIFT_COUNTER] = drift_counter + 1
    else:
        hass.data[DOMAIN][DRIFT_COUNTER] = 0

    _LOGGER.debug(f"Drift: {total_drift}s, Counter: {drift_counter}, Adjusted: {clock_adjusted}")
    return clock_adjusted


def decode_inverter_model(hex_value):
    if isinstance(hex_value, str):
        hex_value = int(hex_value, 16)
    protocol_version = (hex_value >> 8) & 0xFF
    inverter_model = hex_value & 0xFF
    inverter_models = {
        0x00: "No definition",
        0x10: "1-Phase Grid-Tied Inverter (0.7-8K1P / 7-10K1P)",
        0x20: "3-Phase Grid-Tied Inverter (3-20K 3P)",
        0x21: "3-Phase Grid-Tied Inverter (25-50K / 50-70K / 80-110K / 90-136K / 125K / 250K)",
        0x30: "1-Phase LV Hybrid Inverter",
        0x31: "1-Phase LV AC Coupled Energy Storage Inverter",
        0x32: "5-15kWh All-in-One Hybrid",
        0x40: "1-Phase HV Hybrid Inverter",
        0x50: "3-Phase LV Hybrid Inverter",
        0x60: "3-Phase HV Hybrid Inverter (5G)",
        0x70: "S6 3-Phase HV Hybrid (5-10kW)",
        0x71: "S6 3-Phase HV Hybrid (12-20kW)",
        0x72: "S6 3-Phase LV Hybrid (10-15kW)",
        0x73: "S6 3-Phase HV Hybrid (50kW)",
        0x80: "1-Phase HV Hybrid Inverter (S6)",
        0x90: "1-Phase LV Hybrid Inverter (S6)",
        0x91: "S6 1-Phase LV AC Coupled Hybrid",
        0xA0: "OGI Off-Grid Inverter",
        0xA1: "S6 1-Phase LV Off-Grid Hybrid",
    }
    model_description = inverter_models.get(inverter_model, "Unknown Model")
    return protocol_version, model_description


def register_cache_key(controller, register: str | int) -> str:
    conn = getattr(controller, "connection_id", None)
    if not isinstance(conn, str):
        conn = str(getattr(controller, "host", "") or "")
    slave = int(getattr(controller, "device_id", 1))
    return f"{conn}|{slave}|{register}"


def cache_save(hass: HomeAssistant, controller, register: str | int, value):
    hass.data[DOMAIN][VALUES][register_cache_key(controller, register)] = value


def cache_get(hass: HomeAssistant, controller, register: str | int):
    return hass.data[DOMAIN][VALUES].get(register_cache_key(controller, register), None)


def mark_platform_entities_unavailable_for_base_sensors(hass: HomeAssistant, disabled_sensors: list) -> None:
    if not disabled_sensors:
        return
    disabled_set = frozenset(disabled_sensors)
    domain_data = hass.data.get(DOMAIN) or {}
    for bucket in (SENSOR_ENTITIES, NUMBER_ENTITIES):
        for ent in domain_data.get(bucket) or []:
            base = getattr(ent, "base_sensor", None)
            if base is not None and base in disabled_set:
                ent._attr_available = False
                ent.schedule_update_ha_state()


def set_controller(hass: HomeAssistant, controller, config_entry: ConfigEntry):
    hass.data[DOMAIN][CONTROLLER][config_entry.entry_id] = controller


def get_controller_from_entry(hass: HomeAssistant, config_entry: ConfigEntry):
    return hass.data[DOMAIN][CONTROLLER].get(config_entry.entry_id)


def get_controller(hass: HomeAssistant, host: str, slave: int = 1):
    for controller in hass.data[DOMAIN][CONTROLLER].values():
        if getattr(controller, "host", None) == host and getattr(controller, "device_id", 0) == slave:
            return controller
    return None


def split_s32(s32_values: list[int]):
    high_word = s32_values[0] - (1 << 16) if s32_values[0] & (1 << 15) else s32_values[0]
    low_word = s32_values[1] - (1 << 16) if s32_values[1] & (1 << 15) else s32_values[1]
    return (high_word << 16) | (low_word & 0xFFFF)


def _any_in(target: list[int], collection: set[int]) -> bool:
    return any(item in collection for item in target)


def is_correct_controller(controller, host: str, slave: int):
    return controller.host == host and controller.device_id == slave


def register_update_signal(controller, register: int) -> str:
    cid = getattr(controller, "connection_id", None)
    if isinstance(cid, str):
        scope = f"{cid}_{int(controller.device_id)}"
    elif isinstance(getattr(controller, "connection_type", None), str) and controller.connection_type == CONN_TYPE_TCP:
        scope = f"{controller.host}_{int(controller.port)}_{int(controller.device_id)}"
    else:
        scope = f"{controller.host}_{int(controller.device_id)}"
    return f"{DOMAIN}_{scope}_{int(register)}"


def notify_register_update(hass: HomeAssistant, controller, register: int, value) -> None:
    payload = {
        REGISTER: register,
        VALUE: value,
        CONTROLLER: controller.host,
        SLAVE: int(controller.device_id),
    }
    async_dispatcher_send(hass, register_update_signal(controller, register), payload)
