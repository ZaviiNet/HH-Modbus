import asyncio
import logging
import time

from pymodbus.client import AsyncModbusSerialClient, AsyncModbusTcpClient

from custom_components.hh_modbus_control.const import CONN_TYPE_SERIAL, CONN_TYPE_TCP

_LOGGER = logging.getLogger(__name__)


class ModbusClientManager:
    _instance = None

    def __init__(self):
        self._clients: dict[str, dict] = {}

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def get_tcp_client(self, host: str, port: int) -> AsyncModbusTcpClient:
        key = f"{host}:{port}"
        if key not in self._clients:
            _LOGGER.debug(f"Creating new Modbus TCP client for {host}:{port}")
            client = AsyncModbusTcpClient(host=host, port=port, timeout=5, retries=5)
            self._clients[key] = {
                "client": client,
                "ref_count": 0,
                "lock": asyncio.Lock(),
                "type": CONN_TYPE_TCP,
                "last_modbus_request": 0.0,
            }

        self._clients[key]["ref_count"] += 1
        _LOGGER.debug(f"TCP client ref count for {host}:{port} is now {self._clients[key]['ref_count']}")
        return self._clients[key]["client"]

    def get_serial_client(self, serial_port: str, baudrate: int, bytesize: int, parity: str, stopbits: int) -> AsyncModbusSerialClient:
        key = serial_port
        if key not in self._clients:
            _LOGGER.debug(f"Creating new Modbus Serial client for {serial_port} (baudrate={baudrate})")
            client = AsyncModbusSerialClient(port=serial_port, baudrate=baudrate, bytesize=bytesize, parity=parity, stopbits=stopbits, timeout=5)
            self._clients[key] = {
                "client": client,
                "ref_count": 0,
                "lock": asyncio.Lock(),
                "type": CONN_TYPE_SERIAL,
                "last_modbus_request": 0.0,
            }

        self._clients[key]["ref_count"] += 1
        _LOGGER.debug(f"Serial client ref count for {serial_port} is now {self._clients[key]['ref_count']}")
        return self._clients[key]["client"]

    def get_client_lock(self, connection_id: str) -> asyncio.Lock:
        if connection_id in self._clients:
            return self._clients[connection_id]["lock"]
        return None

    def get_last_modbus_request(self, connection_id: str) -> float:
        if connection_id in self._clients:
            return float(self._clients[connection_id].get("last_modbus_request", 0.0))
        return 0.0

    async def inter_frame_wait(self, connection_id: str, is_write: bool = False) -> None:
        if connection_id not in self._clients:
            return
        delay_ms = 100 if is_write else 50
        entry = self._clients[connection_id]
        current_time = time.perf_counter()
        last = float(entry.get("last_modbus_request", 0.0))
        elapsed = (current_time - last) * 1000
        if elapsed < delay_ms:
            await asyncio.sleep((delay_ms - elapsed) / 1000)
        entry["last_modbus_request"] = time.perf_counter()

    def release_client(self, connection_id: str):
        if connection_id in self._clients:
            self._clients[connection_id]["ref_count"] -= 1
            _LOGGER.debug(f"Client ref count for {connection_id} is now {self._clients[connection_id]['ref_count']}")

            if self._clients[connection_id]["ref_count"] <= 0:
                _LOGGER.debug(f"Closing and removing Modbus client for {connection_id}")
                client = self._clients[connection_id]["client"]
                if client.connected:
                    client.close()
                del self._clients[connection_id]
