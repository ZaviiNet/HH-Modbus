"""Config flow for HH Modbus Control — supports Solis and Sun-Synk/Deye inverters."""

import asyncio
import logging
import re

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import OptionsFlowWithConfigEntry

from .const import (
    BRAND_LABELS,
    BRAND_SOLIS,
    BRAND_SUNSYNK,
    CONF_BAUDRATE,
    CONF_BYTESIZE,
    CONF_CONNECTION_TYPE,
    CONF_INVERTER_SERIAL,
    CONF_PARITY,
    CONF_SERIAL_PORT,
    CONF_STOPBITS,
    CONN_TYPE_SERIAL,
    CONN_TYPE_TCP,
    DEFAULT_BAUDRATE,
    DEFAULT_BYTESIZE,
    DEFAULT_PARITY,
    DEFAULT_STOPBITS,
    DOMAIN,
    INVERTER_BRAND,
)
from .data.solis_config import CONNECTION_METHOD, SOLIS_INVERTERS, InverterConfig, inverter_options_from_config
from .data.sunsynk_config import SUNSYNK_INVERTERS, SunsynkInverterConfig
from .modbus_controller import ModbusController

_LOGGER = logging.getLogger(__name__)

# Model dictionaries
SOLIS_MODELS = {inv.model: inv.model for inv in SOLIS_INVERTERS}
SUNSYNK_MODELS = {inv.model: inv.model for inv in SUNSYNK_INVERTERS}

# Connection type options
CONNECTION_TYPES = {CONN_TYPE_TCP: "TCP (WiFi Dongle)", CONN_TYPE_SERIAL: "Serial (RS485)"}

# Parity options
PARITY_OPTIONS = {"N": "None", "E": "Even", "O": "Odd"}


_MAX_CONNECTION_ATTEMPTS = 5


def clean_identification(iden: str | None) -> str | None:
    if not iden or not iden.strip():
        return None
    iden = iden.strip().lower()
    iden = re.sub(r"[^a-z0-9_]", "_", iden)
    return re.sub(r"_+", "_", iden).strip("_")


def _solis_config_schema(connection_type: str) -> dict:
    base = {
        vol.Required(CONF_INVERTER_SERIAL): str,
        vol.Required("slave", default=1): int,
        vol.Optional("identification", default=""): str,
        vol.Optional("poll_interval_fast", default=10): vol.All(int, vol.Range(min=5)),
        vol.Optional("poll_interval_normal", default=15): vol.All(int, vol.Range(min=10)),
        vol.Optional("poll_interval_slow", default=30): vol.All(int, vol.Range(min=15)),
        vol.Required("model", default=list(SOLIS_MODELS.keys())[0]): vol.In(SOLIS_MODELS),
        vol.Required("has_v2", default=True): bool,
        vol.Required("has_pv", default=True): bool,
        vol.Required("has_battery", default=True): bool,
        vol.Required("has_hv_battery", default=False): bool,
        vol.Required("has_generator", default=True): bool,
        vol.Required("has_ac_coupling", default=False): bool,
        vol.Required("has_parallel", default=False): bool,
    }
    if connection_type == CONN_TYPE_TCP:
        base[vol.Required("host", default="")] = str
        base[vol.Required("port", default=502)] = int
        base[vol.Required("connection", default=list(CONNECTION_METHOD.keys())[0])] = vol.In(CONNECTION_METHOD)
    else:
        base[vol.Required(CONF_SERIAL_PORT, default="/dev/ttyUSB0")] = str
        base[vol.Required(CONF_BAUDRATE, default=DEFAULT_BAUDRATE)] = vol.In([9600, 19200, 38400, 57600, 115200])
        base[vol.Required(CONF_BYTESIZE, default=DEFAULT_BYTESIZE)] = vol.In([7, 8])
        base[vol.Required(CONF_PARITY, default=DEFAULT_PARITY)] = vol.In(PARITY_OPTIONS)
        base[vol.Required(CONF_STOPBITS, default=DEFAULT_STOPBITS)] = vol.In([1, 2])
    return base


def _sunsynk_config_schema(connection_type: str) -> dict:
    base = {
        vol.Required(CONF_INVERTER_SERIAL): str,
        vol.Required("slave", default=1): int,
        vol.Optional("identification", default=""): str,
        vol.Optional("poll_interval_fast", default=10): vol.All(int, vol.Range(min=5)),
        vol.Optional("poll_interval_normal", default=15): vol.All(int, vol.Range(min=10)),
        vol.Optional("poll_interval_slow", default=30): vol.All(int, vol.Range(min=15)),
        vol.Required("model", default=list(SUNSYNK_MODELS.keys())[0]): vol.In(SUNSYNK_MODELS),
    }
    if connection_type == CONN_TYPE_TCP:
        base[vol.Required("host", default="")] = str
        base[vol.Required("port", default=502)] = int
    else:
        base[vol.Required(CONF_SERIAL_PORT, default="/dev/ttyUSB0")] = str
        base[vol.Required(CONF_BAUDRATE, default=DEFAULT_BAUDRATE)] = vol.In([9600, 19200, 38400, 57600, 115200])
        base[vol.Required(CONF_BYTESIZE, default=DEFAULT_BYTESIZE)] = vol.In([7, 8])
        base[vol.Required(CONF_PARITY, default=DEFAULT_PARITY)] = vol.In(PARITY_OPTIONS)
        base[vol.Required(CONF_STOPBITS, default=DEFAULT_STOPBITS)] = vol.In([1, 2])
    return base


class HHModbusConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """HH Modbus Control configuration flow."""

    VERSION = 1
    MINOR_VERSION = 0

    def __init__(self):
        """Initialize the config flow."""
        self._brand: str | None = None
        self._connection_type: str | None = None

    async def async_step_user(self, user_input=None):
        """Step 1: Choose inverter brand."""
        errors = {}

        if user_input is not None:
            brand = user_input.get(INVERTER_BRAND)
            if brand in (BRAND_SOLIS, BRAND_SUNSYNK):
                self._brand = brand
                return await self.async_step_connection()
            errors["base"] = "invalid_brand"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(INVERTER_BRAND, default=BRAND_SOLIS): vol.In(BRAND_LABELS),
                }
            ),
            errors=errors,
        )

    async def async_step_connection(self, user_input=None):
        """Step 2: Choose connection type."""
        errors = {}

        if user_input is not None:
            conn_type = user_input.get(CONF_CONNECTION_TYPE)
            if conn_type in (CONN_TYPE_TCP, CONN_TYPE_SERIAL):
                self._connection_type = conn_type
                return await self.async_step_config()
            errors["base"] = "invalid_connection"

        return self.async_show_form(
            step_id="connection",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_CONNECTION_TYPE, default=CONN_TYPE_TCP): vol.In(CONNECTION_TYPES),
                }
            ),
            errors=errors,
        )

    async def async_step_config(self, user_input=None):
        """Step 3: Brand-specific configuration."""
        errors = {}

        if user_input is not None:
            full_config = {
                INVERTER_BRAND: self._brand,
                CONF_CONNECTION_TYPE: self._connection_type,
                **user_input,
            }
            # Clean identification
            full_config["identification"] = clean_identification(full_config.get("identification"))

            if CONF_INVERTER_SERIAL in full_config:
                full_config[CONF_INVERTER_SERIAL] = str(full_config[CONF_INVERTER_SERIAL]).strip().upper()

            valid, err_msg = await self._validate_config(full_config)
            if valid:
                serial = full_config[CONF_INVERTER_SERIAL]
                await self.async_set_unique_id(serial)
                self._abort_if_unique_id_configured()
                brand_label = BRAND_LABELS.get(self._brand, self._brand)
                return self.async_create_entry(
                    title=f"{brand_label}: {serial}",
                    data=full_config,
                )
            errors["base"] = err_msg or "cannot_connect"

        if self._brand == BRAND_SUNSYNK:
            schema_dict = _sunsynk_config_schema(self._connection_type)
        else:
            schema_dict = _solis_config_schema(self._connection_type)

        return self.async_show_form(
            step_id="config",
            data_schema=vol.Schema(schema_dict),
            errors=errors,
        )

    async def async_step_reconfigure(self, user_input=None):
        """Handle reconfiguration of an existing entry."""
        errors = {}
        entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        current_config = {**entry.data, **entry.options}

        brand = current_config.get(INVERTER_BRAND, BRAND_SOLIS)
        conn_type = current_config.get(CONF_CONNECTION_TYPE, CONN_TYPE_TCP)

        if user_input is not None:
            data = {**current_config, **user_input}
            data["identification"] = clean_identification(data.get("identification"))
            if CONF_INVERTER_SERIAL in data:
                data[CONF_INVERTER_SERIAL] = str(data[CONF_INVERTER_SERIAL]).strip().upper()

            valid, err_msg = await self._validate_config(data)
            if valid:
                return self.async_update_reload_and_abort(entry, data=data)
            errors["base"] = err_msg or "cannot_connect"

        if brand == BRAND_SUNSYNK:
            schema_dict = _sunsynk_config_schema(conn_type)
        else:
            schema_dict = _solis_config_schema(conn_type)

        schema_with_suggestions = self.add_suggested_values_to_schema(vol.Schema(schema_dict), current_config)

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=schema_with_suggestions,
            errors=errors,
        )

    async def _validate_config(self, user_input: dict) -> tuple[bool, str | None]:
        """Validate by attempting to connect and read a register.

        Returns (True, None) on success, (False, error_key) on failure.
        """
        brand = user_input.get(INVERTER_BRAND, BRAND_SOLIS)
        conn_type = user_input.get(CONF_CONNECTION_TYPE, CONN_TYPE_TCP)

        if brand == BRAND_SUNSYNK:
            inverter_model = user_input.get("model")
            inverter_config: SunsynkInverterConfig | None = next(
                (inv for inv in SUNSYNK_INVERTERS if inv.model == inverter_model), None
            )
            if inverter_config is None:
                return False, "invalid_model"
        else:
            inverter_model = user_input.get("model")
            inverter_template: InverterConfig | None = next(
                (inv for inv in SOLIS_INVERTERS if inv.model == inverter_model), None
            )
            if inverter_template is None:
                return False, "invalid_model"
            user_options = inverter_options_from_config(user_input, inverter_template)
            inverter_config = inverter_template.clone_with_options(
                user_options, user_input.get("connection", "S2_WL_ST")
            )

        controller_params = {
            "hass": self.hass,
            "device_id": user_input.get("slave", 1),
            "identification": clean_identification(user_input.get("identification")),
            "fast_poll": user_input.get("poll_interval_fast", 10),
            "normal_poll": user_input.get("poll_interval_normal", 15),
            "slow_poll": user_input.get("poll_interval_slow", 30),
            "inverter_config": inverter_config,
            "connection_type": conn_type,
        }

        if conn_type == CONN_TYPE_TCP:
            controller_params["host"] = user_input.get("host", "")
            controller_params["port"] = user_input.get("port", 502)
        else:
            controller_params["serial_port"] = user_input.get(CONF_SERIAL_PORT, "/dev/ttyUSB0")
            controller_params["baudrate"] = user_input.get(CONF_BAUDRATE, DEFAULT_BAUDRATE)
            controller_params["bytesize"] = user_input.get(CONF_BYTESIZE, DEFAULT_BYTESIZE)
            controller_params["parity"] = user_input.get(CONF_PARITY, DEFAULT_PARITY)
            controller_params["stopbits"] = user_input.get(CONF_STOPBITS, DEFAULT_STOPBITS)

        modbus_controller = ModbusController(**controller_params)

        for attempt in range(_MAX_CONNECTION_ATTEMPTS):
            try:
                if not await modbus_controller.connect():
                    raise ConnectionError("Failed to connect")

                if brand == BRAND_SUNSYNK:
                    # Sun-Synk: read input register 0 (device type)
                    await modbus_controller.async_read_input_register(0, 1)
                else:
                    from .data.enums import InverterType

                    if inverter_config.type in [InverterType.GRID, InverterType.STRING]:
                        await modbus_controller.async_read_input_register(3041, 1)
                    else:
                        await modbus_controller.async_read_input_register(35000, 1)

                return True, None
            except Exception as e:
                _LOGGER.warning("Connection attempt %d/5 failed: %s", attempt + 1, e)
                if attempt < _MAX_CONNECTION_ATTEMPTS - 1:
                    await asyncio.sleep(1)
            finally:
                modbus_controller.close_connection()

        _LOGGER.error("All 5 connection attempts failed for: %s", controller_params)
        return False, "cannot_connect"

    @staticmethod
    @config_entries.HANDLERS.register(DOMAIN)
    def async_get_options_flow(config_entry):
        """Return the options flow handler."""
        return HHModbusOptionsFlowHandler(config_entry)


class HHModbusOptionsFlowHandler(OptionsFlowWithConfigEntry):
    """Handle options flow for HH Modbus Control."""

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        errors = {}
        current = {**self.config_entry.data, **self.config_entry.options}
        brand = current.get(INVERTER_BRAND, BRAND_SOLIS)

        if user_input is not None:
            merged = {**self.config_entry.options, **user_input}
            return self.async_create_entry(title="", data=merged)

        if brand == BRAND_SUNSYNK:
            options_schema = vol.Schema(
                {
                    vol.Required("poll_interval_fast"): vol.All(int, vol.Range(min=5)),
                    vol.Required("poll_interval_normal"): vol.All(int, vol.Range(min=10)),
                    vol.Required("poll_interval_slow"): vol.All(int, vol.Range(min=15)),
                    vol.Required("model"): vol.In(SUNSYNK_MODELS),
                }
            )
        else:
            options_schema = vol.Schema(
                {
                    vol.Required("poll_interval_fast"): vol.All(int, vol.Range(min=5)),
                    vol.Required("poll_interval_normal"): vol.All(int, vol.Range(min=10)),
                    vol.Required("poll_interval_slow"): vol.All(int, vol.Range(min=15)),
                    vol.Required("model"): vol.In(SOLIS_MODELS),
                    vol.Required("connection", default=list(CONNECTION_METHOD.keys())[0]): vol.In(CONNECTION_METHOD),
                    vol.Required("has_v2", default=True): bool,
                    vol.Required("has_pv", default=True): bool,
                    vol.Required("has_battery", default=True): bool,
                    vol.Required("has_hv_battery", default=False): bool,
                    vol.Required("has_generator", default=True): bool,
                    vol.Required("has_ac_coupling", default=False): bool,
                    vol.Required("has_parallel", default=False): bool,
                }
            )

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(options_schema, current),
            errors=errors,
        )
