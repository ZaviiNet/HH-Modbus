import logging

from homeassistant.config_entries import ConfigEntry

from custom_components.hh_modbus_control.modbus_controller import ModbusController
from custom_components.hh_modbus_control.const import DOMAIN, NUMBER_ENTITIES
from custom_components.hh_modbus_control.helpers import get_controller_from_entry
from custom_components.hh_modbus_control.sensors.solis_number_sensor import SolisNumberEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry: ConfigEntry, async_add_devices):
    controller: ModbusController = get_controller_from_entry(hass, config_entry)

    sensors: list[SolisNumberEntity] = []
    for sensor_group in controller.sensor_groups:
        for sensor in sensor_group.sensors:
            if sensor.name != "reserve" and sensor.editable:
                sensors.append(SolisNumberEntity(hass, sensor))
    hass.data.setdefault(DOMAIN, {})[NUMBER_ENTITIES] = sensors
    _LOGGER.info(f"Number entities = {len(sensors)}")
    async_add_devices(sensors, True)
    return True
