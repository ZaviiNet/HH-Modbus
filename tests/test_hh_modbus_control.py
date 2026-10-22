"""Tests for the HH Modbus Control multi-brand integration and the ported upstream features."""

from unittest.mock import patch

import pytest
from homeassistant import config_entries, data_entry_flow
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hh_modbus_control.config_flow import (
    HHModbusConfigFlow,
    _is_supported_serial_port,
    _validate_poll_interval,
)
from custom_components.hh_modbus_control.const import (
    BRAND_GIVENERGY,
    BRAND_SOLIS,
    CONF_CONNECTION_TYPE,
    CONN_TYPE_TCP,
    DOMAIN,
    INVERTER_BRAND,
    POLL_PROFILE_EXTREME,
    POLL_PROFILE_FULL,
)


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


def test_serial_proxy_and_port_helpers():
    """Upstream serial-proxy support is available to the fork."""
    from custom_components.hh_modbus_control.serial_proxy import is_serial_proxy

    assert is_serial_proxy("esphome-hass://aux-2/0")
    assert _is_supported_serial_port("/dev/ttyUSB0")
    assert _is_supported_serial_port("socket://192.168.1.50:8899")
    assert _is_supported_serial_port("esphome-hass://aux-2/0")
    assert not _is_supported_serial_port("http://example.com")


def test_poll_interval_floor_by_profile():
    """The ported poll-profile floor logic works in the fork."""
    assert _validate_poll_interval({"poll_interval_fast": 10, "poll_profile": POLL_PROFILE_FULL}) is None
    assert _validate_poll_interval({"poll_interval_fast": 2, "poll_profile": POLL_PROFILE_FULL}) == "poll_interval_below_floor"
    assert _validate_poll_interval({"poll_interval_fast": 2, "poll_profile": POLL_PROFILE_EXTREME}) is None


async def _run_solis_flow(hass: HomeAssistant, data: dict):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert result["step_id"] == "user"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], user_input={INVERTER_BRAND: BRAND_SOLIS})
    assert result["step_id"] == "connection"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], user_input={CONF_CONNECTION_TYPE: CONN_TYPE_TCP})
    assert result["step_id"] == "config"
    return await hass.config_entries.flow.async_configure(result["flow_id"], user_input=data)


@pytest.mark.asyncio
async def test_solis_config_flow_includes_ported_options(hass: HomeAssistant):
    """The Solis branch exposes serial-proxy-era and poll-profile fields."""
    data = {
        "host": "1.2.3.4",
        "port": 502,
        "slave": 1,
        "inverter_serial": "sn123",
        "identification": "",
        "poll_interval_fast": 10,
        "poll_interval_normal": 15,
        "poll_interval_slow": 30,
        "poll_profile": POLL_PROFILE_FULL,
        "extreme_include_battery": False,
        "extreme_include_smart_port": False,
        "suppress_night_offline_issue": False,
        "clock_sync": True,
        "model": "S6-EH1P",
        "connection": "S2_WL_ST",
        "has_v2": True,
        "has_pv": True,
        "has_ac_coupling": False,
        "has_parallel": False,
        "has_battery": True,
        "has_hv_battery": False,
        "has_generator": False,
        "has_dual_meter": False,
        "has_epm": True,
    }
    with patch.object(HHModbusConfigFlow, "_validate_config", return_value=(True, None)) as validate:
        result = await _run_solis_flow(hass, data)

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == "Solis: SN123"
    assert result["data"][INVERTER_BRAND] == BRAND_SOLIS
    assert result["data"]["inverter_serial"] == "SN123"
    assert result["data"]["poll_profile"] == POLL_PROFILE_FULL
    assert result["data"]["has_dual_meter"] is False
    validate.assert_called()


@pytest.mark.asyncio
async def test_generic_brand_config_flow(hass: HomeAssistant):
    """A non-Solis brand still uses the fork's brand/connection/config steps."""
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], user_input={INVERTER_BRAND: BRAND_GIVENERGY})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], user_input={CONF_CONNECTION_TYPE: CONN_TYPE_TCP})
    assert result["step_id"] == "config"

    data = {
        "host": "1.2.3.5",
        "port": 8899,
        "slave": 1,
        "inverter_serial": "giv123",
        "identification": "",
        "poll_interval_fast": 10,
        "poll_interval_normal": 15,
        "poll_interval_slow": 30,
        "model": "GivEnergy-Hybrid-1P",
    }
    with patch.object(HHModbusConfigFlow, "_validate_config", return_value=(True, None)):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], user_input=data)

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == "GivEnergy: GIV123"
    assert result["data"][INVERTER_BRAND] == BRAND_GIVENERGY


def _solis_entry(hass: HomeAssistant) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="SN123456",
        version=1,
        minor_version=0,
        data={
            INVERTER_BRAND: BRAND_SOLIS,
            CONF_CONNECTION_TYPE: CONN_TYPE_TCP,
            "host": "1.2.3.4",
            "port": 502,
            "slave": 1,
            "inverter_serial": "SN123456",
            "model": "S6-EH1P",
            "has_pv": True,
            "has_generator": False,
            "has_hv_battery": False,
            "has_v2": True,
            "has_dual_meter": False,
            "has_epm": True,
            "poll_interval_fast": 10,
            "poll_interval_normal": 15,
            "poll_interval_slow": 30,
            "poll_profile": POLL_PROFILE_FULL,
        },
        title="Solis Inverter",
    )
    entry.add_to_hass(hass)
    return entry


@pytest.mark.asyncio
async def test_solis_setup_and_upstream_features(hass: HomeAssistant):
    """The Solis entry loads with the merged sensor set (incl. Grid Import/Export Power)."""
    entry = _solis_entry(hass)
    with (
        patch("custom_components.hh_modbus_control.modbus_controller.ModbusController.connect", return_value=True),
        patch("custom_components.hh_modbus_control.modbus_controller.ModbusController.connected", return_value=True),
        patch(
            "custom_components.hh_modbus_control.modbus_controller.ModbusController.async_read_input_register",
            return_value=[1, 2, 3],
        ),
        patch(
            "custom_components.hh_modbus_control.modbus_controller.ModbusController.async_read_holding_register",
            return_value=[1, 2, 3],
        ),
        patch("custom_components.hh_modbus_control.modbus_controller.ModbusController.process_write_queue"),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert entry.state.value == "loaded"
        runtime = entry.runtime_data
        assert runtime is not None
        assert runtime.controller is not None
        assert runtime.data_retrieval is not None
        assert runtime.entities["sensor"]
        assert runtime.entities["sensor_derived"]
        entity_names = {entity.name for entity in runtime.entities["sensor"] + runtime.entities["sensor_derived"]}
        assert {"Grid Import Power", "Grid Export Power"} <= entity_names

        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
        assert getattr(entry, "runtime_data", None) is None


@pytest.mark.asyncio
async def test_generic_brand_setup(hass: HomeAssistant):
    """A non-Solis brand sets up through the fork's sensor-only path."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="GIV123456",
        version=1,
        minor_version=0,
        data={
            INVERTER_BRAND: BRAND_GIVENERGY,
            CONF_CONNECTION_TYPE: CONN_TYPE_TCP,
            "host": "1.2.3.5",
            "port": 8899,
            "slave": 1,
            "inverter_serial": "GIV123456",
            "model": "GivEnergy-Hybrid-1P",
            "poll_interval_fast": 10,
            "poll_interval_normal": 15,
            "poll_interval_slow": 30,
        },
        title="GivEnergy Inverter",
    )
    entry.add_to_hass(hass)
    with (
        patch("custom_components.hh_modbus_control.modbus_controller.ModbusController.connect", return_value=True),
        patch("custom_components.hh_modbus_control.modbus_controller.ModbusController.connected", return_value=True),
        patch(
            "custom_components.hh_modbus_control.modbus_controller.ModbusController.async_read_input_register",
            return_value=[1, 2, 3],
        ),
        patch(
            "custom_components.hh_modbus_control.modbus_controller.ModbusController.async_read_holding_register",
            return_value=[1, 2, 3],
        ),
        patch("custom_components.hh_modbus_control.modbus_controller.ModbusController.process_write_queue"),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert entry.state.value == "loaded"
        assert entry.runtime_data is not None
        assert entry.runtime_data.controller.manufacturer == "GivEnergy"
        assert entry.runtime_data.entities["sensor"]

        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
