import logging
from datetime import UTC, datetime, time

from homeassistant.components.sensor import RestoreSensor, SensorDeviceClass
from homeassistant.components.time import TimeEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from custom_components.hh_modbus_control.modbus_controller import ModbusController
from custom_components.hh_modbus_control.const import CONTROLLER, DOMAIN, REGISTER, SLAVE, TIME_ENTITIES, VALUE
from custom_components.hh_modbus_control.helpers import (
    cache_get,
    get_controller_from_entry,
    is_correct_controller,
    register_update_signal,
    unique_id_generator,
)
from custom_components.hh_modbus_control.sensor_data.time_sensors import get_time_sensors

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry: ConfigEntry, async_add_devices):
    modbus_controller: ModbusController = get_controller_from_entry(hass, config_entry)

    inverter_config = modbus_controller.inverter_config

    time_entities: list[SolisTimeEntity] = []
    time_definitions = get_time_sensors(inverter_config)

    for entity_definition in time_definitions:
        time_entities.append(SolisTimeEntity(hass, modbus_controller, entity_definition))
    hass.data[DOMAIN][TIME_ENTITIES] = time_entities
    async_add_devices(time_entities, True)


class SolisTimeEntity(RestoreSensor, TimeEntity):

    def __init__(self, hass, modbus_controller, entity_definition):
        self._hass = hass
        self._modbus_controller = modbus_controller
        self._register: int = entity_definition["register"]

        self._attr_unique_id = unique_id_generator(modbus_controller, entity_definition.get("unique", "reserve"))
        self._attr_name = entity_definition["name"]
        self._attr_has_entity_name = True
        self._attr_available = True
        self._attr_device_class = entity_definition.get("device_class", None)

        self._received_values = {}

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        state = await self.async_get_last_sensor_data()
        if state:
            self._attr_native_value = state.native_value

        self.async_on_remove(
            async_dispatcher_connect(
                self._hass,
                register_update_signal(self._modbus_controller, self._register),
                self.handle_modbus_update,
            )
        )
        self.async_on_remove(
            async_dispatcher_connect(
                self._hass,
                register_update_signal(self._modbus_controller, self._register + 1),
                self.handle_modbus_update,
            )
        )

    @callback
    def handle_modbus_update(self, data):
        updated_register = int(data.get(REGISTER))
        updated_controller = str(data.get(CONTROLLER))
        updated_controller_slave = int(data.get(SLAVE))

        if not is_correct_controller(self._modbus_controller, updated_controller, updated_controller_slave):
            return

        if updated_register in (self._register, self._register + 1):
            value = data.get(VALUE)
            if self._attr_device_class == SensorDeviceClass.TIMESTAMP:
                updated_value = value if isinstance(value, datetime) else datetime.now(UTC)
            else:
                updated_value = int(value)
            self._received_values[updated_register] = updated_value

            if updated_value is not None:
                hour = cache_get(self._hass, self._modbus_controller, self._register)
                minute = cache_get(self._hass, self._modbus_controller, self._register + 1)

                if hour is not None and minute is not None:
                    hour, minute = int(hour), int(minute)
                    if 0 <= minute <= 59 and 0 <= hour <= 23:
                        self._attr_native_value = time(hour=hour, minute=minute)
                        self._attr_available = True
                    else:
                        self._attr_available = False
                else:
                    self._attr_available = False

                self.schedule_update_ha_state()

    @property
    def device_info(self):
        return self._modbus_controller.device_info

    async def async_set_value(self, value: time) -> None:
        await self._modbus_controller.async_write_holding_registers(self._register, [value.hour, value.minute])
        self._attr_native_value = value
        self.async_write_ha_state()
