"""The HH Modbus Control Integration — supports multiple inverter brands via Modbus."""

import asyncio
import logging
from datetime import datetime

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers.device_registry import DeviceEntry

from .const import (
    BRAND_DURACELL,
    BRAND_GIVENERGY,
    BRAND_SIGENERGY,
    BRAND_SOLIS,
    BRAND_SOLAREDGE,
    BRAND_SKYLINE,
    BRAND_SUNSYNK,
    CONF_BAUDRATE,
    CONF_BYTESIZE,
    CONF_CONNECTION_TYPE,
    CONF_INVERTER_SERIAL,
    CONF_PARITY,
    CONF_SERIAL_PORT,
    CONF_SLAVE,
    CONF_STOPBITS,
    CONN_TYPE_SERIAL,
    CONN_TYPE_TCP,
    CONTROLLER,
    DEFAULT_BAUDRATE,
    DEFAULT_BYTESIZE,
    DEFAULT_PARITY,
    DEFAULT_STOPBITS,
    DOMAIN,
    INVERTER_BRAND,
    MANUFACTURER_DURACELL,
    MANUFACTURER_GIVENERGY,
    MANUFACTURER_SIGENERGY,
    MANUFACTURER_SOLIS,
    MANUFACTURER_SOLAREDGE,
    MANUFACTURER_SKYLINE,
    MANUFACTURER_SUNSYNK,
    TIME_ENTITIES,
)
from .data_retrieval import DataRetrieval
from .helpers import get_controller, set_controller, unique_id_generator
from .modbus_controller import ModbusController
from .sensors.solis_base_sensor import SolisBaseSensor, SolisSensorGroup

_LOGGER = logging.getLogger(__name__)

# Platforms loaded for Solis inverters (full feature set)
SOLIS_PLATFORMS = [Platform.NUMBER, Platform.SWITCH, Platform.TIME, Platform.SELECT]
# Platforms loaded for Sun-Synk inverters — NUMBER for editable holding-register sensors;
# TIME/SELECT/SWITCH are Solis-specific so are skipped.
SUNSYNK_PLATFORMS = [Platform.NUMBER]
# New brands: sensor-only for initial release
SENSOR_ONLY_PLATFORMS: list[Platform] = []

SCHEME_HOLDING_REGISTER = vol.Schema(
    {
        vol.Required("address"): vol.Coerce(int),
        vol.Required("value"): vol.Coerce(int),
        vol.Optional("host"): vol.Coerce(str),
    }
)
SCHEME_TIME_SET = vol.Schema(
    {vol.Required("entity_id"): vol.Coerce(str), vol.Required("time"): vol.Coerce(str)}
)


async def async_remove_config_entry_device(
    hass: HomeAssistant, config_entry: ConfigEntry, device_entry: DeviceEntry
) -> bool:
    """Remove a config entry from a device."""
    return True


async def async_setup(hass: HomeAssistant, entry: ConfigEntry):
    """Set up the HH Modbus Control integration."""

    def service_write_holding_register(call: ServiceCall):
        address = call.data.get("address")
        value = call.data.get("value")
        host = call.data.get("host")
        slave = call.data.get("slave", 1)

        if host:
            controller = get_controller(hass, host, slave)
            hass.create_task(controller.async_write_holding_register(int(address), int(value)))
        else:
            for controller in hass.data[DOMAIN][CONTROLLER].values():
                hass.create_task(controller.async_write_holding_register(int(address), int(value)))

    async def service_set_time(call: ServiceCall) -> None:
        """Service to update a time entity."""
        entity_id = call.data.get("entity_id")
        time_str = call.data.get("time")

        if not entity_id or not time_str:
            _LOGGER.error("Missing entity_id or time parameter in service call")
            return

        try:
            try:
                new_time = datetime.strptime(time_str, "%H:%M:%S").time()
            except ValueError:
                new_time = datetime.strptime(time_str, "%H:%M").time()
        except Exception as e:
            _LOGGER.error("❌ Failed to parse time string '%s': %s", time_str, e)
            return

        for entity in call.hass.data.get(DOMAIN, {}).get(TIME_ENTITIES, []):
            if entity.entity_id == entity_id:
                await entity.async_set_value(new_time)
                _LOGGER.debug("Set time for %s to %s", entity_id, new_time)
                return

        _LOGGER.error("⚠️ Entity with id %s not found in %s TIME_ENTITIES", entity_id, DOMAIN)

    hass.services.async_register(
        DOMAIN, "write_holding_register", service_write_holding_register, schema=SCHEME_HOLDING_REGISTER
    )
    hass.services.async_register(DOMAIN, "set_time", service_set_time, schema=SCHEME_TIME_SET)

    return True


async def async_update_options(entry):
    """Handle options updates."""
    hass = entry.hass
    await hass.config_entries.async_update_entry(entry, options=entry.options)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up HH Modbus Control from a config entry."""

    config = {**entry.data, **entry.options}
    slave = config.get(CONF_SLAVE, 1)
    inverter_serial = config.get(CONF_INVERTER_SERIAL)
    brand = config.get(INVERTER_BRAND, BRAND_SOLIS)

    if not inverter_serial:
        hass.components.persistent_notification.async_create(
            "HH Modbus Control: Inverter Serial is missing. Please reconfigure the integration.",
            title="HH Modbus Control Configuration Issue",
            notification_id="hh_modbus_missing_serial",
        )
        raise ConfigEntryError("Inverter Serial is missing")

    connection_type = config.get(CONF_CONNECTION_TYPE, CONN_TYPE_TCP if "host" in config else CONN_TYPE_SERIAL)

    host = config.get("host")
    port = config.get("port", 502)

    if connection_type == CONN_TYPE_TCP:
        connection_id = f"{host}:{port}"
    else:
        serial_port = config.get(CONF_SERIAL_PORT, "/dev/ttyUSB0")
        connection_id = serial_port

    _LOGGER.debug(config)

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN].setdefault(CONTROLLER, {})

    existing_same_link = sum(
        1 for c in hass.data[DOMAIN][CONTROLLER].values() if getattr(c, "connection_id", None) == connection_id
    )
    if existing_same_link:
        delay_s = min(1.5 * existing_same_link, 5.0)
        _LOGGER.debug(
            "Staggering startup: %s existing controller(s) on %s, waiting %.1fs",
            existing_same_link,
            connection_id,
            delay_s,
        )
        await asyncio.sleep(delay_s)

    poll_interval_fast = config.get("poll_interval_fast", 5)
    poll_interval_normal = config.get("poll_interval_normal", 15)
    poll_interval_slow = config.get("poll_interval_slow", 30)
    identification = config.get("identification", None)

    if brand == BRAND_SUNSYNK:
        await _setup_sunsynk_entry(hass, entry, config, connection_type, host, port, slave, inverter_serial, identification, poll_interval_fast, poll_interval_normal, poll_interval_slow)
    elif brand == BRAND_GIVENERGY:
        await _setup_generic_entry(hass, entry, config, connection_type, host, port, slave, inverter_serial, identification, poll_interval_fast, poll_interval_normal, poll_interval_slow, brand)
    elif brand == BRAND_SIGENERGY:
        await _setup_generic_entry(hass, entry, config, connection_type, host, port, slave, inverter_serial, identification, poll_interval_fast, poll_interval_normal, poll_interval_slow, brand)
    elif brand == BRAND_SOLAREDGE:
        await _setup_generic_entry(hass, entry, config, connection_type, host, port, slave, inverter_serial, identification, poll_interval_fast, poll_interval_normal, poll_interval_slow, brand)
    elif brand == BRAND_SKYLINE:
        await _setup_generic_entry(hass, entry, config, connection_type, host, port, slave, inverter_serial, identification, poll_interval_fast, poll_interval_normal, poll_interval_slow, brand)
    elif brand == BRAND_DURACELL:
        await _setup_generic_entry(hass, entry, config, connection_type, host, port, slave, inverter_serial, identification, poll_interval_fast, poll_interval_normal, poll_interval_slow, brand)
    else:
        await _setup_solis_entry(hass, entry, config, connection_type, host, port, slave, inverter_serial, identification, poll_interval_fast, poll_interval_normal, poll_interval_slow)

    return True


async def _setup_solis_entry(
    hass, entry, config, connection_type, host, port, slave, inverter_serial, identification, poll_interval_fast, poll_interval_normal, poll_interval_slow
):
    """Set up a Solis inverter entry."""
    from .data.solis_config import SOLIS_INVERTERS, InverterConfig, inverter_options_from_config
    from .data.enums import InverterType

    inverter_model = config.get("model")
    if inverter_model is None:
        old_type = config.get("type", "hybrid")
        inverter_model = "S6-EH3P" if old_type == "hybrid" else ("WAVESHARE" if old_type == "hybrid-waveshare" else "S6-GR1P")

    inverter_template: InverterConfig | None = next((inv for inv in SOLIS_INVERTERS if inv.model == inverter_model), None)

    if inverter_template is None:
        hass.components.persistent_notification.async_create(
            "HH Modbus Control: Your Solis inverter configuration is invalid. Please reconfigure the integration.",
            title="HH Modbus Control Configuration Issue",
            notification_id="hh_modbus_invalid_config",
        )
        raise ConfigEntryError

    user_options = inverter_options_from_config(config, inverter_template)
    inverter_config = inverter_template.clone_with_options(user_options, config.get("connection", "S2_WL_ST"))

    _LOGGER.info(
        "Loaded HH Modbus Control - Solis (%s) with Model: %s", connection_type, config.get("model")
    )

    if inverter_config.type in [InverterType.STRING, InverterType.GRID]:
        from .sensor_data.string_sensors import string_sensors as sensors
        from .sensor_data.string_sensors import string_sensors_derived as sensors_derived
    else:
        from .sensor_data.hybrid_sensors import hybrid_sensors as sensors
        from .sensor_data.hybrid_sensors import hybrid_sensors_derived as sensors_derived

    controller_params = {
        "hass": hass,
        "device_id": slave,
        "identification": identification,
        "fast_poll": poll_interval_fast,
        "normal_poll": poll_interval_normal,
        "slow_poll": poll_interval_slow,
        "inverter_config": inverter_config,
        "connection_type": connection_type,
        "serial_number": inverter_serial,
        "manufacturer": MANUFACTURER_SOLIS,
    }

    if connection_type == CONN_TYPE_TCP:
        controller_params["host"] = host
        controller_params["port"] = port
    else:
        controller_params["serial_port"] = config.get(CONF_SERIAL_PORT, "/dev/ttyUSB0")
        controller_params["baudrate"] = config.get(CONF_BAUDRATE, DEFAULT_BAUDRATE)
        controller_params["bytesize"] = config.get(CONF_BYTESIZE, DEFAULT_BYTESIZE)
        controller_params["parity"] = config.get(CONF_PARITY, DEFAULT_PARITY)
        controller_params["stopbits"] = config.get(CONF_STOPBITS, DEFAULT_STOPBITS)

    controller = ModbusController(**controller_params)

    controller._sensor_groups = []
    for group in sensors:
        feature_requirement = group.get("feature_requirement", [])
        if feature_requirement and not any(feature in inverter_config.features for feature in feature_requirement):
            group_name = group.get("name", group.get("register_start", "Unnamed"))
            _LOGGER.warning(
                f"Skipping sensor group '{group_name}' due to missing required features: {feature_requirement}"
            )
            continue
        controller._sensor_groups.append(
            SolisSensorGroup(hass=hass, definition=group, controller=controller, identification=identification)
        )

    controller._derived_sensors = [
        SolisBaseSensor(
            hass=hass,
            name=entity.get("name"),
            controller=controller,
            registrars=[int(r) for r in entity.get("register", [])],
            write_register=entity.get("write_register", None),
            state_class=entity.get("state_class", None),
            device_class=entity.get("device_class", None),
            unit_of_measurement=entity.get("unit_of_measurement", None),
            multiplier=entity.get("multiplier", 1),
            editable=entity.get("editable", False),
            hidden=entity.get("hidden", False),
            category=entity.get("category", None),
            unique_id=unique_id_generator(controller, entity.get("unique", "reserve")),
        )
        for entity in sensors_derived
    ]

    set_controller(hass, controller, entry)

    _LOGGER.debug(
        f"Solis config entry setup for {connection_type} connection, slave {slave}"
    )

    await hass.config_entries.async_forward_entry_setups(entry, [Platform.SENSOR])
    await hass.config_entries.async_forward_entry_setups(entry, SOLIS_PLATFORMS)

    hass.data[DOMAIN].setdefault("data_retrieval", {})
    hass.data[DOMAIN]["data_retrieval"][entry.entry_id] = DataRetrieval(hass, controller)


async def _setup_sunsynk_entry(
    hass, entry, config, connection_type, host, port, slave, inverter_serial, identification, poll_interval_fast, poll_interval_normal, poll_interval_slow
):
    """Set up a Sun-Synk/Deye inverter entry."""
    from .data.sunsynk_config import SUNSYNK_INVERTERS, SunsynkInverterConfig

    inverter_model = config.get("model")
    inverter_config: SunsynkInverterConfig | None = next(
        (inv for inv in SUNSYNK_INVERTERS if inv.model == inverter_model), None
    )

    if inverter_config is None:
        hass.components.persistent_notification.async_create(
            "HH Modbus Control: Your Sun-Synk inverter configuration is invalid. Please reconfigure the integration.",
            title="HH Modbus Control Configuration Issue",
            notification_id="hh_modbus_sunsynk_invalid_config",
        )
        raise ConfigEntryError

    _LOGGER.info(
        "Loaded HH Modbus Control - Sun-Synk (%s) with Model: %s", connection_type, inverter_model
    )

    from .sensor_data.sunsynk_single_phase import sunsynk_single_phase_sensors as sensors

    controller_params = {
        "hass": hass,
        "device_id": slave,
        "identification": identification,
        "fast_poll": poll_interval_fast,
        "normal_poll": poll_interval_normal,
        "slow_poll": poll_interval_slow,
        "inverter_config": inverter_config,
        "connection_type": connection_type,
        "serial_number": inverter_serial,
        "manufacturer": MANUFACTURER_SUNSYNK,
    }

    if connection_type == CONN_TYPE_TCP:
        controller_params["host"] = host
        controller_params["port"] = port
    else:
        controller_params["serial_port"] = config.get(CONF_SERIAL_PORT, "/dev/ttyUSB0")
        controller_params["baudrate"] = config.get(CONF_BAUDRATE, DEFAULT_BAUDRATE)
        controller_params["bytesize"] = config.get(CONF_BYTESIZE, DEFAULT_BYTESIZE)
        controller_params["parity"] = config.get(CONF_PARITY, DEFAULT_PARITY)
        controller_params["stopbits"] = config.get(CONF_STOPBITS, DEFAULT_STOPBITS)

    controller = ModbusController(**controller_params)

    controller._sensor_groups = []
    for group in sensors:
        controller._sensor_groups.append(
            SolisSensorGroup(hass=hass, definition=group, controller=controller, identification=identification)
        )

    controller._derived_sensors = []

    set_controller(hass, controller, entry)

    _LOGGER.debug(
        f"Sun-Synk config entry setup for {connection_type} connection, slave {slave}"
    )

    await hass.config_entries.async_forward_entry_setups(entry, [Platform.SENSOR])
    # Sun-Synk: number/switch/time/select platforms are Solis-specific; skip for now
    await hass.config_entries.async_forward_entry_setups(entry, SUNSYNK_PLATFORMS)

    hass.data[DOMAIN].setdefault("data_retrieval", {})
    hass.data[DOMAIN]["data_retrieval"][entry.entry_id] = DataRetrieval(hass, controller)


async def _setup_generic_entry(
    hass, entry, config, connection_type, host, port, slave, inverter_serial, identification,
    poll_interval_fast, poll_interval_normal, poll_interval_slow, brand: str,
):
    """Set up a generic (non-Solis/non-SunSynk) brand inverter entry using sensor-only platform."""
    # Resolve inverter config & sensor list based on brand
    if brand == BRAND_GIVENERGY:
        from .data.givenergy_config import GIVENERGY_INVERTERS
        from .sensor_data.givenergy_sensors import givenergy_sensors as sensors
        inverter_model = config.get("model", "GivEnergy-Hybrid-1P")
        inverter_config = next((inv for inv in GIVENERGY_INVERTERS if inv.model == inverter_model), GIVENERGY_INVERTERS[0])
        manufacturer = MANUFACTURER_GIVENERGY
        brand_label = "GivEnergy"
    elif brand == BRAND_SIGENERGY:
        from .data.sigenergy_config import SIGENERGY_INVERTERS
        from .sensor_data.sigenergy_sensors import sigenergy_sensors as sensors
        inverter_model = config.get("model", "Sigenergy-5K")
        inverter_config = next((inv for inv in SIGENERGY_INVERTERS if inv.model == inverter_model), SIGENERGY_INVERTERS[0])
        manufacturer = MANUFACTURER_SIGENERGY
        brand_label = "Sigenergy"
    elif brand == BRAND_SOLAREDGE:
        from .data.solaredge_config import SOLAREDGE_INVERTERS
        from .sensor_data.solaredge_sensors import solaredge_sensors as sensors
        inverter_model = config.get("model", "SolarEdge-Single-Phase")
        inverter_config = next((inv for inv in SOLAREDGE_INVERTERS if inv.model == inverter_model), SOLAREDGE_INVERTERS[0])
        manufacturer = MANUFACTURER_SOLAREDGE
        brand_label = "SolarEdge"
    elif brand == BRAND_SKYLINE:
        from .data.skyline_config import SKYLINE_INVERTERS
        from .sensor_data.skyline_sensors import skyline_sensors as sensors
        inverter_model = config.get("model", "Skyline-5K")
        inverter_config = next((inv for inv in SKYLINE_INVERTERS if inv.model == inverter_model), SKYLINE_INVERTERS[0])
        manufacturer = MANUFACTURER_SKYLINE
        brand_label = "Skyline"
    elif brand == BRAND_DURACELL:
        from .data.skyline_config import SKYLINE_INVERTERS
        from .sensor_data.skyline_sensors import duracell_g3_sensors as sensors
        inverter_model = config.get("model", "Duracell-G3-5K")
        inverter_config = next((inv for inv in SKYLINE_INVERTERS if inv.model == inverter_model), SKYLINE_INVERTERS[4])
        manufacturer = MANUFACTURER_DURACELL
        brand_label = "Duracell G3"
    else:
        raise ConfigEntryError(f"Unknown brand: {brand}")

    _LOGGER.info(
        "Loaded HH Modbus Control - %s (%s) with Model: %s", brand_label, connection_type, inverter_model
    )

    controller_params = {
        "hass": hass,
        "device_id": slave,
        "identification": identification,
        "fast_poll": poll_interval_fast,
        "normal_poll": poll_interval_normal,
        "slow_poll": poll_interval_slow,
        "inverter_config": inverter_config,
        "connection_type": connection_type,
        "serial_number": inverter_serial,
        "manufacturer": manufacturer,
    }

    if connection_type == CONN_TYPE_TCP:
        controller_params["host"] = host
        controller_params["port"] = port
    else:
        controller_params["serial_port"] = config.get(CONF_SERIAL_PORT, "/dev/ttyUSB0")
        controller_params["baudrate"] = config.get(CONF_BAUDRATE, DEFAULT_BAUDRATE)
        controller_params["bytesize"] = config.get(CONF_BYTESIZE, DEFAULT_BYTESIZE)
        controller_params["parity"] = config.get(CONF_PARITY, DEFAULT_PARITY)
        controller_params["stopbits"] = config.get(CONF_STOPBITS, DEFAULT_STOPBITS)

    controller = ModbusController(**controller_params)

    controller._sensor_groups = []
    for group in sensors:
        controller._sensor_groups.append(
            SolisSensorGroup(hass=hass, definition=group, controller=controller, identification=identification)
        )

    controller._derived_sensors = []

    set_controller(hass, controller, entry)

    _LOGGER.debug(
        "%s config entry setup for %s connection, slave %s", brand_label, connection_type, slave
    )

    await hass.config_entries.async_forward_entry_setups(entry, [Platform.SENSOR])
    # New brands: sensor-only for initial release; control platforms planned
    await hass.config_entries.async_forward_entry_setups(entry, SENSOR_ONLY_PLATFORMS)

    hass.data[DOMAIN].setdefault("data_retrieval", {})
    hass.data[DOMAIN]["data_retrieval"][entry.entry_id] = DataRetrieval(hass, controller)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a HH Modbus Control config entry."""
    _LOGGER.debug("init async_unload_entry")

    config = {**entry.data, **entry.options}
    brand = config.get(INVERTER_BRAND, BRAND_SOLIS)
    if brand == BRAND_SOLIS:
        extra_platforms = SOLIS_PLATFORMS
    elif brand == BRAND_SUNSYNK:
        extra_platforms = SUNSYNK_PLATFORMS
    else:
        extra_platforms = SENSOR_ONLY_PLATFORMS
    platforms = [Platform.SENSOR] + extra_platforms

    unload_ok = all(
        await asyncio.gather(
            *(hass.config_entries.async_forward_entry_unload(entry, platform) for platform in platforms)
        )
    )

    if unload_ok:
        if "data_retrieval" in hass.data[DOMAIN]:
            data_retrieval = hass.data[DOMAIN]["data_retrieval"].pop(entry.entry_id, None)
            if data_retrieval:
                await data_retrieval.async_stop()

        if CONTROLLER in hass.data[DOMAIN]:
            controller = hass.data[DOMAIN][CONTROLLER].pop(entry.entry_id, None)
            if controller:
                _LOGGER.debug("Closing Modbus connection for entry %s", entry.entry_id)
                controller.close_connection()

    return unload_ok
