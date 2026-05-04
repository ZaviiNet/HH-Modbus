import decimal
import fractions
import logging
import numbers
from datetime import UTC, datetime

from homeassistant.components.sensor import RestoreSensor, SensorDeviceClass, SensorEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from custom_components.hh_modbus_control.const import CONTROLLER, REGISTER, SLAVE, VALUE
from custom_components.hh_modbus_control.helpers import clock_drift_test, decode_inverter_model, is_correct_controller, register_update_signal
from custom_components.hh_modbus_control.sensors.solis_base_sensor import SolisBaseSensor

_LOGGER = logging.getLogger(__name__)

# Import status mapping only if available (Solis-specific)
try:
    from custom_components.hh_modbus_control.data.status_mapping import STATUS_MAPPING
except ImportError:
    STATUS_MAPPING = {}


class SolisDerivedSensor(RestoreSensor, SensorEntity):

    def __init__(self, hass: HomeAssistant, sensor: SolisBaseSensor):
        self._hass = hass if hass else sensor.hass
        self.base_sensor = sensor

        self._attr_name = sensor.name
        self._attr_has_entity_name = True
        self._attr_unique_id = sensor.unique_id

        self._register: list[int] = sensor.registrars

        self._device_class = sensor.device_class
        self._unit_of_measurement = sensor.unit_of_measurement
        self._attr_device_class = sensor.device_class
        self._attr_state_class = sensor.state_class
        self._attr_native_unit_of_measurement = sensor.unit_of_measurement
        self._attr_available = not sensor.hidden

        self.is_added_to_hass = False
        self._state = None
        self._received_values = {}

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        state = await self.async_get_last_sensor_data()
        if state:
            if self.base_sensor.device_class != SensorDeviceClass.TIMESTAMP:
                self._attr_native_value = state.native_value
            else:
                self._attr_native_value = datetime.now(UTC)
        self.is_added_to_hass = True

        for reg in set(self._register):
            self.async_on_remove(
                async_dispatcher_connect(
                    self._hass,
                    register_update_signal(self.base_sensor.controller, reg),
                    self.handle_modbus_update,
                )
            )

    @callback
    def handle_modbus_update(self, data):
        updated_register = int(data.get(REGISTER))
        updated_controller = str(data.get(CONTROLLER))
        updated_controller_slave = int(data.get(SLAVE))

        if not is_correct_controller(self.base_sensor.controller, updated_controller, updated_controller_slave):
            return

        if updated_register in self._register:
            self._received_values[updated_register] = data.get(VALUE)

            filtered_registers = {reg for reg in self._register if reg not in (0, 1, 90007)}
            if not all(reg in self._received_values for reg in filtered_registers):
                return

            if 90007 in self._register:
                is_adjusted = clock_drift_test(
                    self.hass,
                    self.base_sensor.controller,
                    self._received_values[33025],
                    self._received_values[33026],
                    self._received_values[33027],
                )
                if is_adjusted:
                    self._attr_available = True
                    self._attr_native_value = datetime.now(UTC)
                    self.schedule_update_ha_state()
                    self._received_values.clear()

            if 90006 in self._register:
                new_value = self.base_sensor.controller.last_modbus_success
                if new_value == 0 or new_value is None:
                    return
                self._attr_available = True
                self._attr_native_value = new_value
                self.schedule_update_ha_state()
                self._received_values.clear()
                return

            new_value = self.base_sensor.get_value

            if 33095 in self._register and STATUS_MAPPING:
                new_value = round(self.base_sensor.get_value)
                new_value = STATUS_MAPPING.get(new_value, "Unknown")

            if 33049 in self._register or 33051 in self._register or 33053 in self._register or 33055 in self._register:
                r1_value = self._received_values[self._register[0]] * self.base_sensor.multiplier
                r2_value = self._received_values[self._register[1]] * self.base_sensor.multiplier
                new_value = round(r1_value * r2_value)

            if 3021 in self._register or 3023 in self._register or 3025 in self._register or 3027 in self._register:
                r1_value = self._received_values[self._register[0]] * self.base_sensor.multiplier
                r2_value = self._received_values[self._register[1]] * self.base_sensor.multiplier
                new_value = round(r1_value * r2_value)

            if 33079 in self._register or 33080 in self._register or 33081 in self._register or 33082 in self._register:
                active_power = self.base_sensor.convert_value([self._received_values[self._register[0]], self._received_values[self._register[1]]])
                reactive_power = self.base_sensor.convert_value([self._received_values[self._register[2]], self._received_values[self._register[3]]])
                if active_power == 0 or reactive_power == 0:
                    new_value = 1
                else:
                    new_value = round(active_power / ((active_power**2 + reactive_power**2) ** 0.5), 3)

            if 33175 in self._register or 33171 in self._register:
                to_grid = self._received_values[self._register[0]] * self.base_sensor.multiplier
                from_grid = self._received_values[self._register[1]] * self.base_sensor.multiplier
                new_value = from_grid - to_grid

            if 35000 in self._register:
                protocol_version, model_description = decode_inverter_model(new_value)
                self.base_sensor.controller._sw_version = protocol_version
                new_value = model_description + f"(Protocol {protocol_version})"

            if isinstance(new_value, (numbers.Number, decimal.Decimal, fractions.Fraction)) or isinstance(new_value, str):
                self._attr_available = True
                self._attr_native_value = new_value
                self._state = new_value
                self.schedule_update_ha_state()

            if new_value is not None:
                self._attr_native_value = new_value
                self.schedule_update_ha_state()

            self._received_values.clear()

    @property
    def device_info(self):
        return self.base_sensor.controller.device_info
