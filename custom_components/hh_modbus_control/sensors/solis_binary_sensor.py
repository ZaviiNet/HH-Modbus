import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.restore_state import RestoreEntity

from custom_components.hh_modbus_control.modbus_controller import ModbusController
from custom_components.hh_modbus_control.const import CONTROLLER, REGISTER, SLAVE, VALUE
from custom_components.hh_modbus_control.helpers import (
    cache_get,
    cache_save,
    is_correct_controller,
    register_update_signal,
    unique_id_generator_binary,
)

_LOGGER = logging.getLogger(__name__)


class SolisBinaryEntity(RestoreEntity, SwitchEntity):
    def __init__(self, hass, modbus_controller, entity_definition):
        self._hass = hass
        self._modbus_controller: ModbusController = modbus_controller
        self._register: int = entity_definition.get("register", entity_definition.get("read_register")) + entity_definition.get("offset", 0)
        write_register = entity_definition.get("write_register", None)
        self._write_register: int = self._register if write_register is None else write_register + entity_definition.get("offset", 0)
        self._bit_position = entity_definition.get("bit_position", None)
        self._conflicts_with = entity_definition.get("conflicts_with", None)
        self._requires = entity_definition.get("requires", None)
        self._requires_any = entity_definition.get("requires_any", None)
        self._on_value = entity_definition.get("on_value", None)
        self._off_value = entity_definition.get("off_value", None)
        self._inverted = entity_definition.get("inverted", None)
        self._attr_unique_id = unique_id_generator_binary(modbus_controller, self._register, self._bit_position, self._on_value)
        self._attr_name = entity_definition["name"]
        self._attr_available = False

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self._hass,
                register_update_signal(self._modbus_controller, self._register),
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

        if updated_register == self._register:
            updated_value = int(data.get(VALUE))

            if self._bit_position is not None:
                bit_bool = get_bit_bool(updated_value, self._bit_position)
                if self._inverted:
                    bit_bool = not bit_bool

            if self._register == 5:
                self._attr_is_on = self._modbus_controller.enabled
                self._attr_available = True
                return self._attr_is_on

            value = updated_value
            if value is None:
                value = cache_get(self._hass, self._modbus_controller, self._register)

            self._attr_available = True
            if self._bit_position is not None:
                raw_bit = get_bit_bool(value, self._bit_position)
                self._attr_is_on = (not raw_bit) if self._inverted else raw_bit
            if self._on_value is not None:
                self._attr_is_on = value == self._on_value

    @property
    def is_on(self):
        return self._attr_is_on

    def turn_on(self, **kwargs: Any) -> None:
        if self._register == 5:
            self._modbus_controller.enable_connection()
        else:
            self.set_register_bit(True)

    def turn_off(self, **kwargs: Any) -> None:
        if self._register == 5:
            self._modbus_controller.disable_connection()
        else:
            self.set_register_bit(False)

    def set_register_bit(self, value: bool):
        controller = self._modbus_controller
        current_register_value: int = cache_get(self._hass, self._modbus_controller, self._register)
        new_register_value = current_register_value

        if self._bit_position is not None:
            if value is True:
                if self._conflicts_with:
                    for cbit in self._conflicts_with:
                        new_register_value = set_bit(new_register_value, cbit, False)
                if self._requires:
                    for rbit in self._requires:
                        new_register_value = set_bit(new_register_value, rbit, True)
                if self._requires_any:
                    if not any(get_bit_bool(current_register_value, r) for r in self._requires_any):
                        new_register_value = set_bit(new_register_value, self._requires_any[0], True)
            bit_to_write = (not value) if self._inverted else value
            new_register_value = set_bit(new_register_value, self._bit_position, bit_to_write)
        else:
            if value is True and self._on_value is not None:
                new_register_value = self._on_value
            elif value is False and self._off_value is not None:
                new_register_value = self._off_value
            else:
                new_register_value = int(value)

        if current_register_value != new_register_value and controller.connected():
            target_register = self._write_register
            self._hass.create_task(controller.async_write_holding_register(target_register, new_register_value))
            cache_save(self._hass, self._modbus_controller, target_register, new_register_value)

        self._attr_is_on = value
        self._attr_available = True

    @property
    def device_info(self):
        return self._modbus_controller.device_info


def set_bit(value, bit_position, new_bit_value):
    if value is None:
        value = 0
    mask = 1 << bit_position
    value &= ~mask
    if new_bit_value:
        value |= mask
    return round(value)


def get_bit_bool(modbus_value, bit_position):
    return (modbus_value >> bit_position) & 1 == 1
