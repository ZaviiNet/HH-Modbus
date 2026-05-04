import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from custom_components.hh_modbus_control.modbus_controller import ModbusController
from custom_components.hh_modbus_control.helpers import get_controller_from_entry
from custom_components.hh_modbus_control.sensor_data.select_sensors import get_select_sensors
from custom_components.hh_modbus_control.sensors.solis_select_entity import SolisSelectEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry, async_add_devices) -> None:
    controller: ModbusController = get_controller_from_entry(hass, config_entry)

    sensor_groups = get_select_sensors(controller.inverter_config)

    sensors: list[SolisSelectEntity] = []
    for sensor_group in sensor_groups:
        sensors.append(SolisSelectEntity(hass, controller, sensor_group))
    _LOGGER.info(f"Select entities = {len(sensors)}")
    async_add_devices(sensors, True)
