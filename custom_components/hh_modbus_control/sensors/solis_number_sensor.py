import logging

from homeassistant.components.number import NumberEntity, NumberMode, RestoreNumber
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.template import is_number

from custom_components.hh_modbus_control.const import CONTROLLER, REGISTER, SLAVE, VALUE
from custom_components.hh_modbus_control.helpers import cache_get, is_correct_controller, register_update_signal
from custom_components.hh_modbus_control.sensors.solis_base_sensor import SolisBaseSensor

_LOGGER = logging.getLogger(__name__)


class SolisNumberEntity(RestoreNumber, NumberEntity):

    def __init__(self, hass, sensor: SolisBaseSensor):
        self._hass = hass
        self.base_sensor = sensor

        self._attr_name = sensor.name
        self._attr_has_entity_name = True
        self._attr_unique_id = sensor.unique_id

        self._register: list[int] = sensor.registrars
        self._write_register: int = sensor.write_register if sensor.write_register is not None else self._register[0] if len(self._register) == 1 else None

        self._device_class = sensor.device_class
        self._unit_of_measurement = sensor.unit_of_measurement
        self._attr_device_class = sensor.device_class
        self._attr_state_class = sensor.state_class
        self._attr_native_unit_of_measurement = sensor.unit_of_measurement
        self._attr_available = not sensor.hidden and sensor.enabled

        self._received_values = {}
        self._multiplier = sensor.multiplier

        self._attr_native_value = sensor.default
        self._attr_mode = NumberMode.AUTO
        self._attr_native_min_value = sensor.min_value
        self._attr_native_max_value = sensor.max_value
        self._attr_native_step = sensor.step
        self._attr_step = sensor.step
        self._attr_should_poll = False
        self._attr_entity_registry_enabled_default = sensor.enabled

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        state = await self.async_get_last_number_data()
        if state:
            self._attr_native_value = state.native_value

        for reg in set(self._register):
            self.async_on_remove(
                async_dispatcher_connect(
                    self._hass,
                    register_update_signal(self.base_sensor.controller, reg),
                    self.handle_modbus_update,
                )
            )
        if not self.base_sensor.enabled:
            self._attr_available = False

    @callback
    def handle_modbus_update(self, data):
        updated_register = int(data.get(REGISTER))
        updated_controller = str(data.get(CONTROLLER))
        updated_controller_slave = int(data.get(SLAVE))

        if not is_correct_controller(self.base_sensor.controller, updated_controller, updated_controller_slave):
            return

        if not self.base_sensor.enabled:
            return

        if updated_register in self._register:
            updated_value = int(data.get(VALUE))
            self._received_values[updated_register] = updated_value

            if not all(reg in self._received_values for reg in self._register):
                return

            new_value = self.base_sensor.convert_value([updated_value])
            self._received_values.clear()

            if new_value is not None:
                self._attr_native_value = new_value
                self.schedule_update_ha_state()

    def set_native_value(self, value):
        if self._attr_native_value == value:
            return
        if self._write_register is None:
            return

        register_value = round(value / self._multiplier)
        if self.base_sensor.data_type == "S16":
            register_value = max(-32768, min(32767, register_value))
            register_value &= 0xFFFF

        self._hass.create_task(self.base_sensor.controller.async_write_holding_register(self._write_register, int(register_value)))
        self._attr_native_value = value
        self.schedule_update_ha_state()

    @property
    def device_info(self):
        return self.base_sensor.controller.device_info
