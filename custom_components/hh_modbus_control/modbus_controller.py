import asyncio
import logging
from datetime import UTC, datetime

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.template import is_number
from pymodbus.client import AsyncModbusSerialClient, AsyncModbusTcpClient

from custom_components.hh_modbus_control.client_manager import ModbusClientManager
from custom_components.hh_modbus_control.const import (
    CONN_TYPE_TCP,
    DEFAULT_BAUDRATE,
    DEFAULT_BYTESIZE,
    DEFAULT_PARITY,
    DEFAULT_STOPBITS,
    DOMAIN,
)
from custom_components.hh_modbus_control.data.enums import PollSpeed
from custom_components.hh_modbus_control.helpers import cache_save, notify_register_update
from custom_components.hh_modbus_control.sensors.solis_base_sensor import SolisSensorGroup
from custom_components.hh_modbus_control.sensors.solis_derived_sensor import SolisDerivedSensor

_LOGGER = logging.getLogger(__name__)

RECOVERABLE_REGISTER_READ_EXCEPTIONS = frozenset({2, 3})


def _exception_code_from_modbus_result(result) -> int | None:
    return getattr(result, "exception_code", None)


class ModbusController:
    def __init__(
        self,
        hass,
        inverter_config,
        sensor_groups: list[SolisSensorGroup] = None,
        derived_sensors: list[SolisDerivedSensor] = None,
        device_id=1,
        fast_poll=5,
        normal_poll=15,
        slow_poll=30,
        connection_type=CONN_TYPE_TCP,
        host=None,
        port=502,
        identification=None,
        serial_port=None,
        baudrate=DEFAULT_BAUDRATE,
        bytesize=DEFAULT_BYTESIZE,
        parity=DEFAULT_PARITY,
        stopbits=DEFAULT_STOPBITS,
        serial_number=None,
        manufacturer="Unknown",
    ):
        self.hass = hass
        self.connection_type = connection_type
        self.device_id = device_id
        self.slave = device_id
        self.serial_number = serial_number
        self.identification = identification
        self.manufacturer = manufacturer

        self._client_manager = ModbusClientManager.get_instance()
        manager = self._client_manager

        if connection_type == CONN_TYPE_TCP:
            if not host:
                raise ValueError("host is required for TCP connection")
            self.host = host
            self.port = port
            self.connection_id = f"{host}:{port}"
            self.client: AsyncModbusTcpClient | AsyncModbusSerialClient = manager.get_tcp_client(host, port)
            self.poll_lock = manager.get_client_lock(self.connection_id)
        else:
            if not serial_port:
                raise ValueError("serial_port is required for Serial connection")
            self.serial_port = serial_port
            self.baudrate = baudrate
            self.bytesize = bytesize
            self.parity = parity
            self.stopbits = stopbits
            self.connection_id = serial_port
            self.host = serial_port
            self.client: AsyncModbusTcpClient | AsyncModbusSerialClient = manager.get_serial_client(serial_port, baudrate, bytesize, parity, stopbits)
            self.poll_lock = manager.get_client_lock(self.connection_id)

        self.connect_failures = 0
        self._data_received = False
        self._poll_interval_fast = fast_poll
        self._poll_interval_normal = normal_poll
        self._poll_interval_slow = slow_poll
        self._model = inverter_config.model
        self.inverter_config = inverter_config
        self._sw_version = "N/A"
        self.enabled = True
        self._last_attempt = 0
        self._sensor_groups = sensor_groups
        self._derived_sensors = derived_sensors

        self.write_queue = asyncio.Queue()
        self._last_modbus_success = datetime.now(UTC)

    async def process_write_queue(self):
        while True:
            if not self.connected():
                await asyncio.sleep(5)
                continue
            if self.write_queue.empty():
                await asyncio.sleep(0.2)
                continue
            write_request = await self.write_queue.get()
            register, value, multiple = write_request
            if multiple:
                await self._execute_write_holding_registers(register, value)
            else:
                await self._execute_write_holding_register(register, value)
            self.write_queue.task_done()

    async def _execute_write_holding_register(self, register, value):
        try:
            await self.connect()
            async with self.poll_lock:
                await self.inter_frame_wait(is_write=True)
                int_value = int(value)
                int_register = register if is_number(register) else int(register)
                if self.connection_type == CONN_TYPE_TCP:
                    result = await self.client.write_register(address=int_register, value=int_value, device_id=self.device_id)
                else:
                    self.client.slave = self.device_id
                    result = await self.client.write_register(address=int_register, value=int_value)
                _LOGGER.debug(f"({self.host}.{self.device_id}) Write register={int_register}, value={int_value}: {result}")
                if result.isError():
                    _LOGGER.error(f"({self.host}.{self.device_id}) Failed to write register {register}: {result}")
                    return None
                cache_save(self.hass, self, int_register, result.registers[0])
                notify_register_update(self.hass, self, int_register, result.registers[0])
                return result
        except Exception as e:
            _LOGGER.error(f"Failed to write holding register {register}: {str(e)}")
            return None

    async def _execute_write_holding_registers(self, start_register, values):
        try:
            await self.connect()
            async with self.poll_lock:
                await self.inter_frame_wait(is_write=True)
                if self.connection_type == CONN_TYPE_TCP:
                    result = await self.client.write_registers(address=start_register, values=values, device_id=self.device_id)
                else:
                    self.client.slave = self.device_id
                    result = await self.client.write_registers(address=start_register, values=values)
                if result.isError():
                    _LOGGER.error(f"({self.host}.{self.device_id}) Write block failed: {result}")
                    return None
                for i, value in enumerate(values):
                    reg_addr = start_register + i
                    cache_save(self.hass, self, reg_addr, value)
                    notify_register_update(self.hass, self, reg_addr, value)
                return result
        except Exception as e:
            _LOGGER.error(f"({self.host}.{self.device_id}) Failed to write registers {start_register}-{start_register + len(values) - 1}: {str(e)}")
            return None

    async def async_write_holding_register(self, register, value):
        await self.write_queue.put((register, value, False))

    async def async_write_holding_registers(self, start_register, values):
        await self.write_queue.put((start_register, values, True))

    async def inter_frame_wait(self, is_write=False):
        await self._client_manager.inter_frame_wait(self.connection_id, is_write=is_write)

    async def _async_read_input_register_raw_detailed(self, register: int, count: int, *, quiet: bool = False) -> tuple[list[int] | None, int | None]:
        async with self.poll_lock:
            await self.inter_frame_wait()
            if self.connection_type == CONN_TYPE_TCP:
                result = await self.client.read_input_registers(address=register, count=count, device_id=self.device_id)
            else:
                self.client.slave = self.device_id
                result = await self.client.read_input_registers(address=register, count=count)
            if result.isError():
                exc = _exception_code_from_modbus_result(result)
                log_fn = _LOGGER.debug if quiet else _LOGGER.error
                log_fn(f"({self.host}.{self.device_id}) Failed to read input registers at {register}: {result}")
                return None, exc
            self._last_modbus_success = datetime.now(UTC)
            return result.registers, None

    async def _async_read_input_register_raw(self, register, count):
        registers, _err = await self._async_read_input_register_raw_detailed(register, count, quiet=False)
        return registers

    async def async_read_input_registers_with_exception(self, register: int, count: int) -> tuple[list[int] | None, int | None]:
        try:
            await self.connect()
            return await self._async_read_input_register_raw_detailed(register, count, quiet=False)
        except Exception as e:
            _LOGGER.error(f"({self.host}.{self.device_id}) Exception reading input registers at {register}: {str(e)}")
            return None, None

    async def async_read_input_register(self, register, count):
        try:
            await self.connect()
            return await self._async_read_input_register_raw(register, count)
        except Exception as e:
            _LOGGER.error(f"({self.host}.{self.device_id}) Exception reading input registers at {register}: {str(e)}")
            return None

    async def _async_read_holding_register_raw_detailed(self, register: int, count: int, *, quiet: bool = False) -> tuple[list[int] | None, int | None]:
        async with self.poll_lock:
            await self.inter_frame_wait()
            if self.connection_type == CONN_TYPE_TCP:
                result = await self.client.read_holding_registers(address=register, count=count, device_id=self.device_id)
            else:
                self.client.slave = self.device_id
                result = await self.client.read_holding_registers(address=register, count=count)
            if result.isError():
                exc = _exception_code_from_modbus_result(result)
                log_fn = _LOGGER.debug if quiet else _LOGGER.error
                log_fn(f"({self.host}.{self.device_id}) Failed to read holding registers at {register}: {result}")
                return None, exc
            self._last_modbus_success = datetime.now(UTC)
            return result.registers, None

    async def _async_read_holding_register_raw(self, register, count):
        registers, _err = await self._async_read_holding_register_raw_detailed(register, count, quiet=False)
        return registers

    async def async_read_holding_registers_with_exception(self, register: int, count: int) -> tuple[list[int] | None, int | None]:
        try:
            await self.connect()
            return await self._async_read_holding_register_raw_detailed(register, count, quiet=False)
        except Exception as e:
            _LOGGER.error(f"({self.host}.{self.device_id}) Exception reading holding registers at {register}: {str(e)}")
            return None, None

    async def async_read_holding_register(self, register, count):
        try:
            await self.connect()
            return await self._async_read_holding_register_raw(register, count)
        except Exception as e:
            _LOGGER.error(f"({self.host}.{self.device_id}) Exception reading holding registers at {register}: {str(e)}")
            return None

    async def connect(self):
        if self.connected():
            return True

        async def _try_connect() -> bool:
            try:
                await self.client.connect()
                if self.connected():
                    _LOGGER.info(f"✅ ({self.host}.{self.device_id}) Connected to Modbus device")
                    self.connect_failures = 0
                    return True
                self.connect_failures += 1
                return False
            except Exception as e:
                self.connect_failures += 1
                _LOGGER.debug(f"❌ ({self.host}.{self.device_id}) Connection error: {e}")
                return False

        lock = self.poll_lock
        if lock:
            async with lock:
                if self.connected():
                    return True
                return await _try_connect()
        return await _try_connect()

    def connected(self):
        return self.client.connected if self.client else False

    def disable_connection(self):
        self.enabled = False

    def enable_connection(self):
        self.enabled = True

    def close_connection(self):
        manager = ModbusClientManager.get_instance()
        manager.release_client(self.connection_id)

    @property
    def model(self):
        return self._model

    @property
    def poll_speed(self):
        return {
            PollSpeed.FAST: self._poll_interval_fast,
            PollSpeed.NORMAL: self._poll_interval_normal,
            PollSpeed.SLOW: self._poll_interval_slow,
        }

    @property
    def sw_version(self):
        return self._sw_version

    def replace_sensor_group(self, old_group: SolisSensorGroup, new_groups: list[SolisSensorGroup]) -> None:
        try:
            idx = self._sensor_groups.index(old_group)
        except ValueError:
            return
        self._sensor_groups = self._sensor_groups[:idx] + new_groups + self._sensor_groups[idx + 1:]

    @property
    def sensor_groups(self):
        return self._sensor_groups

    @property
    def derived_sensors(self):
        return self._derived_sensors

    @property
    def sensor_derived_groups(self):
        return self._derived_sensors

    @property
    def last_modbus_request(self):
        return self._client_manager.get_last_modbus_request(self.connection_id)

    @property
    def last_modbus_success(self):
        return self._last_modbus_success

    @property
    def device_serial_number(self):
        return self.serial_number

    @property
    def device_identification(self):
        return self.identification

    @property
    def device_info(self):
        name = f"{self.manufacturer} {self.model}"
        return DeviceInfo(
            identifiers={(DOMAIN, self.serial_number)},
            manufacturer=self.manufacturer,
            model=self.model,
            serial_number=self.serial_number,
            name=name,
            sw_version=self.sw_version,
        )
