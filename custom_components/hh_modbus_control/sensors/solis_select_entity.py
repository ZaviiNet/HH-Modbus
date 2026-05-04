import logging

from homeassistant.components.select import SelectEntity
from homeassistant.helpers.restore_state import RestoreEntity

from custom_components.hh_modbus_control.modbus_controller import ModbusController
from custom_components.hh_modbus_control.helpers import cache_get, cache_save, unique_id_generator

_LOGGER = logging.getLogger(__name__)


class SolisSelectEntity(RestoreEntity, SelectEntity):
    def __init__(self, hass, modbus_controller, entity_definition) -> None:
        self._hass = hass
        self._modbus_controller: ModbusController = modbus_controller
        self._register = entity_definition["register"]
        self._attr_name = entity_definition["name"]
        self._attr_unique_id = unique_id_generator(modbus_controller, entity_definition["register"], "select")

        self._attr_options = [e["name"] for e in entity_definition["entities"]]
        self._attr_options_raw = entity_definition["entities"]
        self._companion_writes = entity_definition.get("companion_writes") or []
        self._current_option = None

    @property
    def current_option(self) -> str | None:
        reg_cache = cache_get(self._hass, self._modbus_controller, self._register)
        if reg_cache is None:
            return

        sorted_options = sorted(self._attr_options_raw, key=lambda e: len(e.get("requires", [])) if "requires" in e else 0, reverse=True)

        for e in sorted_options:
            on_value = e.get("on_value")
            bit_position = e.get("bit_position")
            requires = e.get("requires")

            if on_value is not None:
                if reg_cache == on_value:
                    return e["name"]
            elif bit_position is not None:
                if get_bit_bool(reg_cache, bit_position):
                    if requires:
                        if all(get_bit_bool(reg_cache, rbit) for rbit in requires):
                            return e["name"]
                    else:
                        return e["name"]

        return None

    async def async_select_option(self, option: str) -> None:
        for e in self._attr_options_raw:
            on_value = e.get("on_value", None)
            bit_position = e.get("bit_position", None)
            conflicts_with = e.get("conflicts_with", None)
            requires = e.get("requires", None)

            if e["name"] == option:
                if on_value is not None:
                    await self._modbus_controller.async_write_holding_register(self._register, on_value)
                    await self._write_companions()
                    self._attr_current_option = option
                    self.async_write_ha_state()
                    break
                else:
                    self.set_register_bit(on_value, bit_position, conflicts_with, requires)

    @property
    def device_info(self):
        return self._modbus_controller.device_info

    async def _write_companions(self) -> None:
        for companion_register in self._companion_writes:
            cached = cache_get(self._hass, self._modbus_controller, companion_register)
            if cached is None:
                continue
            await self._modbus_controller.async_write_holding_register(companion_register, cached)

    def set_register_bit(self, on_value, bit_position, conflicts_with, requires):
        controller = self._modbus_controller
        current_register_value: int = cache_get(self._hass, self._modbus_controller, self._register)

        if bit_position is not None:
            if conflicts_with:
                for wbit in conflicts_with:
                    current_register_value = set_bit(current_register_value, wbit, False)
            if requires:
                for rbit in requires:
                    current_register_value = set_bit(current_register_value, rbit, True)
            new_register_value: int = set_bit(current_register_value, bit_position, True)
        else:
            new_register_value: int = on_value

        if current_register_value != new_register_value and controller.connected():
            self._hass.create_task(controller.async_write_holding_register(self._register, new_register_value))
            cache_save(self._hass, self._modbus_controller, self._register, new_register_value)
        self._attr_available = True


def get_bit_bool(modbus_value, bit_position):
    return (modbus_value >> bit_position) & 1 == 1


def set_bit(value, bit_position, new_bit_value):
    if value is None:
        value = 0
    mask = 1 << bit_position
    value &= ~mask
    if new_bit_value:
        value |= mask
    return round(value)
