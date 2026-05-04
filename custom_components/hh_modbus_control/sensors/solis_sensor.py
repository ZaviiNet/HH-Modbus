import logging
from datetime import UTC, datetime, timedelta

from homeassistant.components.sensor import RestoreSensor, SensorEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from custom_components.hh_modbus_control.const import CONTROLLER, REGISTER, SLAVE, VALUE
from custom_components.hh_modbus_control.data.enums import InverterType, PollSpeed
from custom_components.hh_modbus_control.helpers import cache_get, is_correct_controller, register_update_signal
from custom_components.hh_modbus_control.sensors.solis_base_sensor import SolisBaseSensor

_LOGGER = logging.getLogger(__name__)
_WATCHDOG_TIMEOUT_MIN = 10


class SolisSensor(RestoreSensor, SensorEntity):

    def __init__(self, hass: HomeAssistant, sensor: SolisBaseSensor):
        self._hass = hass
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
        self._attr_available = not sensor.hidden and sensor.enabled
        self._attr_suggested_display_precision = self.decimal_count(sensor.multiplier)

        self.is_added_to_hass = False
        self._state = None
        self._received_values = {}
        self.poll_speed = sensor.poll_speed

        self._last_update = datetime.now(UTC).astimezone()
        self._update_timeout = timedelta(minutes=self.base_sensor.controller.poll_speed.get(sensor.poll_speed, 0) + _WATCHDOG_TIMEOUT_MIN)

    def decimal_count(self, number: float) -> int | None:
        if self.device_class is None:
            return None
        if number == int(number):
            return 0
        str_number = str(number).rstrip("0")
        decimal_part = str_number.split(".")[-1]
        return len(decimal_part)

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        state = await self.async_get_last_sensor_data()
        if state:
            self._attr_native_value = state.native_value
        if not self.base_sensor.enabled:
            self._attr_available = False
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

        if not self.base_sensor.enabled:
            return

        if updated_register in self._register:
            if self.base_sensor.controller.inverter_config.type == InverterType.GRID and 3014 == updated_register:
                if cache_get(self.hass, self.base_sensor.controller, 3043) == 2:
                    self._attr_native_value = 0
                    self.schedule_update_ha_state()
                    self._last_update = datetime.now(UTC).astimezone()
                    return

            updated_value = int(data.get(VALUE))
            self._received_values[updated_register] = updated_value

            if not all(reg in self._received_values for reg in self._register):
                return

            values = [self._received_values[reg] for reg in self._register]
            if None in values:
                problematic_regs = {reg: self._received_values.get(reg) for reg in self._register if self._received_values.get(reg) is None}
                if problematic_regs:
                    return

            new_value = self.base_sensor.convert_value(values)
            self._received_values.clear()

            if new_value is not None:
                self._attr_native_value = new_value
                self._attr_available = True
                self._last_update = datetime.now(UTC).astimezone()
                self.schedule_update_ha_state()

    async def async_update(self):
        now = datetime.now(UTC).astimezone()
        if (now - self._last_update > self._update_timeout) and self.poll_speed != PollSpeed.ONCE:
            self._attr_available = False
            self.schedule_update_ha_state()

    @property
    def device_info(self):
        return self.base_sensor.controller.device_info
