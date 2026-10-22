"""Config flow for HH Modbus Control — supports multiple inverter brands via Modbus."""

import asyncio
import logging
import re

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import OptionsFlow
from pymodbus.client import AsyncModbusSerialClient, AsyncModbusTcpClient

from .const import (
    BRAND_DURACELL,
    BRAND_GIVENERGY,
    BRAND_LABELS,
    BRAND_SIGENERGY,
    BRAND_SKYLINE,
    BRAND_SOLAREDGE,
    BRAND_SOLIS,
    BRAND_SUNSYNK,
    CONF_BAUDRATE,
    CONF_BYTESIZE,
    CONF_CLOCK_SYNC,
    CONF_CONNECTION_TYPE,
    CONF_EXTREME_INCLUDE_BATTERY,
    CONF_EXTREME_INCLUDE_SMART_PORT,
    CONF_INVERTER_SERIAL,
    CONF_PARITY,
    CONF_POLL_PROFILE,
    CONF_SERIAL_PORT,
    CONF_STOPBITS,
    CONF_SUPPRESS_NIGHT_OFFLINE_ISSUE,
    CONN_TYPE_SERIAL,
    CONN_TYPE_TCP,
    DEFAULT_BAUDRATE,
    DEFAULT_BYTESIZE,
    DEFAULT_PARITY,
    DEFAULT_STOPBITS,
    DOMAIN,
    INVERTER_BRAND,
    POLL_INTERVAL_FAST_MIN,
    POLL_INTERVAL_FAST_MIN_EXTREME,
    POLL_PROFILE_EXTREME,
    POLL_PROFILE_FULL,
    POLL_PROFILES,
)
from .data.givenergy_config import GIVENERGY_INVERTERS
from .data.sigenergy_config import SIGENERGY_INVERTERS
from .data.skyline_config import SKYLINE_INVERTERS
from .data.solaredge_config import SOLAREDGE_DEFAULT_PORT, SOLAREDGE_INVERTERS
from .data.solis_config import CONNECTION_METHOD, SOLIS_INVERTERS, InverterConfig, inverter_options_from_config
from .data.sunsynk_config import SUNSYNK_INVERTERS, SunsynkInverterConfig
from .serial_proxy import SerialProxyClient, is_serial_proxy

_LOGGER = logging.getLogger(__name__)

# Model dictionaries
SOLIS_MODELS = {inv.model: inv.model for inv in SOLIS_INVERTERS}
SUNSYNK_MODELS = {inv.model: inv.model for inv in SUNSYNK_INVERTERS}
GIVENERGY_MODELS = {inv.model: inv.model for inv in GIVENERGY_INVERTERS}
SIGENERGY_MODELS = {inv.model: inv.model for inv in SIGENERGY_INVERTERS}
SOLAREDGE_MODELS = {inv.model: inv.model for inv in SOLAREDGE_INVERTERS}
SKYLINE_MODELS = {inv.model: inv.model for inv in SKYLINE_INVERTERS if inv.has_dcdc_version}
DURACELL_MODELS = {inv.model: inv.model for inv in SKYLINE_INVERTERS if not inv.has_dcdc_version}

# Connection type options
CONNECTION_TYPES = {CONN_TYPE_TCP: "TCP (WiFi Dongle)", CONN_TYPE_SERIAL: "Serial (RS485)"}

# Parity options
PARITY_OPTIONS = {"N": "None", "E": "Even", "O": "Odd"}

# HA 2026.5+ offers a picker of the serial ports it can see, with a manual-entry
# option for socket:// or rfc2217:// gateways. Older versions get a text field.
try:
    from homeassistant.helpers.selector import SerialPortSelector
except ImportError:  # HA < 2026.5
    SERIAL_PORT_FIELD = {vol.Required(CONF_SERIAL_PORT, default="/dev/ttyUSB0"): str}
else:
    # No default: preselecting a port that may not exist hides the real ones.
    SERIAL_PORT_FIELD = {vol.Required(CONF_SERIAL_PORT): SerialPortSelector()}

# pymodbus opens serial ports with pyserial's serial_for_url, which takes device
# paths and these URL schemes; ESPHome serial proxies go through SerialProxyClient.
# The picker can list other ports neither can open, and offers no filter.
PYSERIAL_URL_SCHEMES = ("alt", "cp2110", "hwgrep", "loop", "rfc2217", "socket", "spy")

# Register and read type used for the connection probe, per brand.
_BRAND_PROBES = {
    BRAND_SUNSYNK: (0, False),
    BRAND_GIVENERGY: (0, False),
    BRAND_SIGENERGY: (30051, True),
    BRAND_SOLAREDGE: (40083, True),
    BRAND_SKYLINE: (8192, True),
    BRAND_DURACELL: (8192, True),
}


def _is_supported_serial_port(port: str) -> bool:
    """Return whether this serial port path or URL can be opened."""
    scheme, separator, _ = port.partition("://")
    return not separator or scheme.lower() in PYSERIAL_URL_SCHEMES or is_serial_proxy(port)


def _validate_poll_interval(config: dict) -> str | None:
    """Enforce the fast-poll floor that applies to the chosen profile.

    The schemas only declare the extreme floor, because the profile is picked on
    the same form and voluptuous can't vary a field's range by another field's
    value. Returns an error key, or None when the interval is acceptable.
    """
    profile = config.get(CONF_POLL_PROFILE, POLL_PROFILE_FULL)
    floor = POLL_INTERVAL_FAST_MIN_EXTREME if profile == POLL_PROFILE_EXTREME else POLL_INTERVAL_FAST_MIN
    interval = config.get("poll_interval_fast")
    if interval is not None and int(interval) < floor:
        return "poll_interval_below_floor"
    return None


async def _probe_tcp_port(host: str, port: int, timeout: float = 5.0) -> tuple[bool, str | None]:
    """Check that something is actually accepting TCP connections on host:port.

    A plain socket open is far cheaper than a Modbus handshake and separates the two
    failure modes cleanly: a refused/timed-out connect means nothing is listening,
    whereas a successful connect that then fails the register probe means Modbus (or
    the slave id) is the problem. Returns (reachable, reason).
    """
    writer = None
    try:
        _, writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout=timeout)
        return True, None
    except TimeoutError:
        return False, "timeout"
    except OSError as e:
        # ConnectionRefusedError, host unreachable, DNS failure — all OSError subclasses.
        return False, type(e).__name__
    finally:
        if writer is not None:
            writer.close()
            try:
                await writer.wait_closed()
            except OSError:  # pragma: no cover - best-effort cleanup
                pass


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
        # Floor is the extreme-profile minimum; _validate_poll_interval enforces the
        # stricter default floor, which voluptuous can't do since the profile is
        # chosen on this same form.
        vol.Optional("poll_interval_fast", default=POLL_INTERVAL_FAST_MIN): vol.All(int, vol.Range(min=POLL_INTERVAL_FAST_MIN_EXTREME)),
        vol.Optional("poll_interval_normal", default=15): vol.All(int, vol.Range(min=15)),
        vol.Optional("poll_interval_slow", default=30): vol.All(int, vol.Range(min=30)),
        vol.Required(CONF_POLL_PROFILE, default=POLL_PROFILE_FULL): vol.In(POLL_PROFILES),
        vol.Required(CONF_EXTREME_INCLUDE_BATTERY, default=False): bool,
        vol.Required(CONF_EXTREME_INCLUDE_SMART_PORT, default=False): bool,
        vol.Required(CONF_SUPPRESS_NIGHT_OFFLINE_ISSUE, default=False): bool,
        vol.Required(CONF_CLOCK_SYNC, default=True): bool,
        vol.Required("model", default=list(SOLIS_MODELS.keys())[0]): vol.In(SOLIS_MODELS),
        vol.Required("has_v2", default=True): bool,
        vol.Required("has_pv", default=True): bool,
        vol.Required("has_battery", default=True): bool,
        vol.Required("has_hv_battery", default=False): bool,
        vol.Required("has_generator", default=True): bool,
        vol.Required("has_ac_coupling", default=False): bool,
        vol.Required("has_parallel", default=False): bool,
        vol.Required("has_dual_meter", default=False): bool,
        vol.Required("has_epm", default=True): bool,
    }
    if connection_type == CONN_TYPE_TCP:
        base[vol.Required("host", default="")] = str
        base[vol.Required("port", default=502)] = int
        base[vol.Required("connection", default=list(CONNECTION_METHOD.keys())[0])] = vol.In(CONNECTION_METHOD)
    else:
        base.update(SERIAL_PORT_FIELD)
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
        base.update(SERIAL_PORT_FIELD)
        base[vol.Required(CONF_BAUDRATE, default=DEFAULT_BAUDRATE)] = vol.In([9600, 19200, 38400, 57600, 115200])
        base[vol.Required(CONF_BYTESIZE, default=DEFAULT_BYTESIZE)] = vol.In([7, 8])
        base[vol.Required(CONF_PARITY, default=DEFAULT_PARITY)] = vol.In(PARITY_OPTIONS)
        base[vol.Required(CONF_STOPBITS, default=DEFAULT_STOPBITS)] = vol.In([1, 2])
    return base


def _simple_brand_config_schema(connection_type: str, models: dict, default_port: int = 502) -> dict:
    """Generic config schema for brands that only need model + connection settings."""
    base = {
        vol.Required(CONF_INVERTER_SERIAL): str,
        vol.Required("slave", default=1): int,
        vol.Optional("identification", default=""): str,
        vol.Optional("poll_interval_fast", default=10): vol.All(int, vol.Range(min=5)),
        vol.Optional("poll_interval_normal", default=15): vol.All(int, vol.Range(min=10)),
        vol.Optional("poll_interval_slow", default=30): vol.All(int, vol.Range(min=15)),
        vol.Required("model", default=list(models.keys())[0]): vol.In(models),
    }
    if connection_type == CONN_TYPE_TCP:
        base[vol.Required("host", default="")] = str
        base[vol.Required("port", default=default_port)] = int
    else:
        base.update(SERIAL_PORT_FIELD)
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
            if brand in BRAND_LABELS:
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
        elif self._brand == BRAND_GIVENERGY:
            schema_dict = _simple_brand_config_schema(self._connection_type, GIVENERGY_MODELS, default_port=8899)
        elif self._brand == BRAND_SIGENERGY:
            schema_dict = _simple_brand_config_schema(self._connection_type, SIGENERGY_MODELS)
        elif self._brand == BRAND_SOLAREDGE:
            schema_dict = _simple_brand_config_schema(self._connection_type, SOLAREDGE_MODELS, default_port=SOLAREDGE_DEFAULT_PORT)
        elif self._brand == BRAND_SKYLINE:
            schema_dict = _simple_brand_config_schema(self._connection_type, SKYLINE_MODELS)
        elif self._brand == BRAND_DURACELL:
            schema_dict = _simple_brand_config_schema(self._connection_type, DURACELL_MODELS)
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

            serial = (data.get(CONF_INVERTER_SERIAL) or "").strip()
            if not serial:
                errors["base"] = "serial_required"
            elif not data.get("model"):
                errors["base"] = "model_required"
            elif any(
                other.unique_id == serial and other.entry_id != entry.entry_id
                for other in self.hass.config_entries.async_entries(DOMAIN)
            ):
                return self.async_abort(reason="already_configured")
            elif brand == BRAND_SOLIS and (interval_error := _validate_poll_interval(data)):
                errors["base"] = interval_error
            else:
                valid, err_msg = await self._validate_config(data)
                if valid:
                    # Strip reconfigured keys from options: setup merges
                    # {**data, **options}, so stale option values would silently
                    # shadow the freshly reconfigured data otherwise.
                    new_options = {k: v for k, v in entry.options.items() if k not in user_input}
                    return self.async_update_reload_and_abort(
                        entry, data=data, options=new_options, unique_id=serial
                    )
                errors["base"] = err_msg or "cannot_connect"

        if brand == BRAND_SUNSYNK:
            schema_dict = _sunsynk_config_schema(conn_type)
        elif brand == BRAND_GIVENERGY:
            schema_dict = _simple_brand_config_schema(conn_type, GIVENERGY_MODELS, default_port=8899)
        elif brand == BRAND_SIGENERGY:
            schema_dict = _simple_brand_config_schema(conn_type, SIGENERGY_MODELS)
        elif brand == BRAND_SOLAREDGE:
            schema_dict = _simple_brand_config_schema(conn_type, SOLAREDGE_MODELS, default_port=SOLAREDGE_DEFAULT_PORT)
        elif brand == BRAND_SKYLINE:
            schema_dict = _simple_brand_config_schema(conn_type, SKYLINE_MODELS)
        elif brand == BRAND_DURACELL:
            schema_dict = _simple_brand_config_schema(conn_type, DURACELL_MODELS)
        else:
            schema_dict = _solis_config_schema(conn_type)

        schema_with_suggestions = self.add_suggested_values_to_schema(vol.Schema(schema_dict), current_config)

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=schema_with_suggestions,
            errors=errors,
        )

    async def _validate_config(self, user_input: dict) -> tuple[bool, str | None]:
        """Validate the configuration by probing the Modbus device.

        Uses a throwaway client on purpose: building a ModbusController here would
        acquire the SHARED client from ModbusClientManager and release it repeatedly,
        closing a running entry's connection out from under it during reconfigure or
        when adding a second inverter on the same datalogger.

        Returns (True, None) on success, (False, error_key) on failure.
        """
        brand = user_input.get(INVERTER_BRAND, BRAND_SOLIS)
        conn_type = user_input.get(CONF_CONNECTION_TYPE, CONN_TYPE_TCP)
        inverter_model = user_input.get("model")

        if brand == BRAND_SOLIS:
            inverter_template: InverterConfig | None = next(
                (inv for inv in SOLIS_INVERTERS if inv.model == inverter_model), None
            )
            if inverter_template is None:
                _LOGGER.warning("Invalid or unknown inverter model: %s", inverter_model)
                return False, "invalid_model"
            user_options = inverter_options_from_config(user_input, inverter_template)
            inverter_config = inverter_template.clone_with_options(user_options, user_input.get("connection", "S2_WL_ST"))
            probe_register, probe_holding = inverter_config.probe_register, False
            if interval_error := _validate_poll_interval(user_input):
                return False, interval_error
        elif brand == BRAND_SUNSYNK:
            inverter_config: SunsynkInverterConfig | None = next(
                (inv for inv in SUNSYNK_INVERTERS if inv.model == inverter_model), None
            )
            if inverter_config is None:
                return False, "invalid_model"
            probe_register, probe_holding = _BRAND_PROBES[brand]
        elif brand == BRAND_GIVENERGY:
            inverter_config = next((inv for inv in GIVENERGY_INVERTERS if inv.model == inverter_model), None)
            if inverter_config is None:
                return False, "invalid_model"
            probe_register, probe_holding = _BRAND_PROBES[brand]
        elif brand == BRAND_SIGENERGY:
            inverter_config = next((inv for inv in SIGENERGY_INVERTERS if inv.model == inverter_model), None)
            if inverter_config is None:
                return False, "invalid_model"
            probe_register, probe_holding = _BRAND_PROBES[brand]
        elif brand == BRAND_SOLAREDGE:
            inverter_config = next((inv for inv in SOLAREDGE_INVERTERS if inv.model == inverter_model), None)
            if inverter_config is None:
                return False, "invalid_model"
            probe_register, probe_holding = _BRAND_PROBES[brand]
        elif brand in (BRAND_SKYLINE, BRAND_DURACELL):
            inverter_config = next((inv for inv in SKYLINE_INVERTERS if inv.model == inverter_model), None)
            if inverter_config is None:
                return False, "invalid_model"
            probe_register, probe_holding = _BRAND_PROBES[brand]
        else:
            return False, "invalid_brand"

        device_id = user_input.get("slave", 1)

        if conn_type == CONN_TYPE_TCP:
            host, port = user_input["host"], user_input.get("port", 502)
            reachable, reason = await _probe_tcp_port(host, port)
            if not reachable:
                # Distinguish "nothing is listening on 502" from "Modbus itself failed".
                # Recent Solis datalogger firmware closes the local TCP services while
                # cloud upload keeps working, which otherwise surfaces as a generic
                # "check your configuration" and sends people hunting the wrong problem
                # (issue #432).
                _LOGGER.error("TCP pre-probe of %s:%s failed (%s) — nothing is serving Modbus there", host, port, reason)
                return False, "tcp_port_closed"
            client = AsyncModbusTcpClient(host=host, port=port, timeout=5, retries=1)
        else:
            if not _is_supported_serial_port(user_input[CONF_SERIAL_PORT]):
                _LOGGER.error("Serial port %s cannot be opened", user_input[CONF_SERIAL_PORT])
                return False, "serial_port_unsupported"
            client_cls = SerialProxyClient if is_serial_proxy(user_input[CONF_SERIAL_PORT]) else AsyncModbusSerialClient
            client = client_cls(
                port=user_input[CONF_SERIAL_PORT],
                baudrate=user_input.get(CONF_BAUDRATE, DEFAULT_BAUDRATE),
                bytesize=user_input.get(CONF_BYTESIZE, DEFAULT_BYTESIZE),
                parity=user_input.get(CONF_PARITY, DEFAULT_PARITY),
                stopbits=user_input.get(CONF_STOPBITS, DEFAULT_STOPBITS),
                timeout=5,
                retries=1,
            )

        try:
            for attempt in range(3):
                try:
                    await client.connect()
                    if not client.connected:
                        raise ConnectionError("Failed to connect")
                    # Both client types take the target unit as `device_id` on the
                    # request itself. Assigning `client.slave` did nothing on the
                    # serial client, so the probe always read device 1 regardless
                    # of the configured slave.
                    if probe_holding:
                        result = await client.read_holding_registers(address=probe_register, count=1, device_id=device_id)
                    else:
                        result = await client.read_input_registers(address=probe_register, count=1, device_id=device_id)
                    if result.isError():
                        raise ConnectionError(f"Probe read of {probe_register} failed: {result}")
                    return True, None
                except Exception as e:
                    _LOGGER.warning("Connection validation attempt %s/3 failed: %s", attempt + 1, e)
                    if attempt < 2:
                        await asyncio.sleep(1)
        finally:
            try:
                client.close()
            except Exception:  # noqa: BLE001 - best-effort cleanup of a throwaway client
                pass

        _LOGGER.error("Connection validation failed after 3 attempts (%s)", conn_type)
        return False, "cannot_connect"

    @staticmethod
    @config_entries.HANDLERS.register(DOMAIN)
    def async_get_options_flow(config_entry):
        """Return the options flow handler."""
        return HHModbusOptionsFlowHandler()


class HHModbusOptionsFlowHandler(OptionsFlow):
    """Handle options flow for HH Modbus Control."""

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        errors = {}
        current = {**self.config_entry.data, **self.config_entry.options}
        brand = current.get(INVERTER_BRAND, BRAND_SOLIS)

        if user_input is not None:
            merged = {**self.config_entry.options, **user_input}
            if brand == BRAND_SOLIS and (interval_error := _validate_poll_interval(merged)):
                errors["base"] = interval_error
            else:
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
        elif brand == BRAND_GIVENERGY:
            options_schema = vol.Schema(
                {
                    vol.Required("poll_interval_fast"): vol.All(int, vol.Range(min=5)),
                    vol.Required("poll_interval_normal"): vol.All(int, vol.Range(min=10)),
                    vol.Required("poll_interval_slow"): vol.All(int, vol.Range(min=15)),
                    vol.Required("model"): vol.In(GIVENERGY_MODELS),
                }
            )
        elif brand == BRAND_SIGENERGY:
            options_schema = vol.Schema(
                {
                    vol.Required("poll_interval_fast"): vol.All(int, vol.Range(min=5)),
                    vol.Required("poll_interval_normal"): vol.All(int, vol.Range(min=10)),
                    vol.Required("poll_interval_slow"): vol.All(int, vol.Range(min=15)),
                    vol.Required("model"): vol.In(SIGENERGY_MODELS),
                }
            )
        elif brand == BRAND_SOLAREDGE:
            options_schema = vol.Schema(
                {
                    vol.Required("poll_interval_fast"): vol.All(int, vol.Range(min=5)),
                    vol.Required("poll_interval_normal"): vol.All(int, vol.Range(min=10)),
                    vol.Required("poll_interval_slow"): vol.All(int, vol.Range(min=15)),
                    vol.Required("model"): vol.In(SOLAREDGE_MODELS),
                }
            )
        elif brand == BRAND_SKYLINE:
            options_schema = vol.Schema(
                {
                    vol.Required("poll_interval_fast"): vol.All(int, vol.Range(min=5)),
                    vol.Required("poll_interval_normal"): vol.All(int, vol.Range(min=10)),
                    vol.Required("poll_interval_slow"): vol.All(int, vol.Range(min=15)),
                    vol.Required("model"): vol.In(SKYLINE_MODELS),
                }
            )
        elif brand == BRAND_DURACELL:
            options_schema = vol.Schema(
                {
                    vol.Required("poll_interval_fast"): vol.All(int, vol.Range(min=5)),
                    vol.Required("poll_interval_normal"): vol.All(int, vol.Range(min=10)),
                    vol.Required("poll_interval_slow"): vol.All(int, vol.Range(min=15)),
                    vol.Required("model"): vol.In(DURACELL_MODELS),
                }
            )
        else:
            options_schema = vol.Schema(
                {
                    vol.Required("poll_interval_fast"): vol.All(int, vol.Range(min=POLL_INTERVAL_FAST_MIN_EXTREME)),
                    vol.Required("poll_interval_normal"): vol.All(int, vol.Range(min=15)),
                    vol.Required("poll_interval_slow"): vol.All(int, vol.Range(min=30)),
                    vol.Required(CONF_POLL_PROFILE, default=POLL_PROFILE_FULL): vol.In(POLL_PROFILES),
                    vol.Required(CONF_EXTREME_INCLUDE_BATTERY, default=False): bool,
                    vol.Required(CONF_EXTREME_INCLUDE_SMART_PORT, default=False): bool,
                    vol.Required(CONF_SUPPRESS_NIGHT_OFFLINE_ISSUE, default=False): bool,
                    vol.Required(CONF_CLOCK_SYNC, default=True): bool,
                    vol.Required("model"): vol.In(SOLIS_MODELS),
                    vol.Required("connection", default=list(CONNECTION_METHOD.keys())[0]): vol.In(CONNECTION_METHOD),
                    vol.Required("has_v2", default=True): bool,
                    vol.Required("has_pv", default=True): bool,
                    vol.Required("has_battery", default=True): bool,
                    vol.Required("has_hv_battery", default=False): bool,
                    vol.Required("has_generator", default=True): bool,
                    vol.Required("has_ac_coupling", default=False): bool,
                    vol.Required("has_parallel", default=False): bool,
                    vol.Required("has_dual_meter", default=False): bool,
                    vol.Required("has_epm", default=True): bool,
                }
            )

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(options_schema, current),
            errors=errors,
        )
