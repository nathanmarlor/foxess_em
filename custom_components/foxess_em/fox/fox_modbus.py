import asyncio
import logging
from typing import Any

from custom_components.foxess_em.const import CONNECTION_TYPE
from custom_components.foxess_em.const import FOX_MODBUS_SERIAL
from custom_components.foxess_em.const import FOX_MODBUS_TCP
from pymodbus.client import ModbusSerialClient
from pymodbus.client import ModbusTcpClient
from pymodbus.exceptions import ModbusException
from pymodbus.exceptions import ModbusIOException

_LOGGER = logging.getLogger(__name__)
_WRITE_ATTEMPTS = 5
_WRITE_ERROR_SLEEP = 5


class FoxModbus:
    """Modbus"""

    def __init__(self, hass, config: dict[str, Any]):
        """Init"""
        self._hass = hass
        self._config = config
        self._write_errors = 0
        self._lock = asyncio.Lock()
        self._config_type = config[CONNECTION_TYPE]
        self._class = {
            FOX_MODBUS_SERIAL: ModbusSerialClient,
            FOX_MODBUS_TCP: ModbusTcpClient,
        }

        self._client = self._class[self._config_type](**config)
        self._hass.async_create_task(self.connect())

    async def connect(self):
        """Connect to device"""
        _LOGGER.debug("Connecting to modbus - (%s)", self._config)
        if not await self._async_pymodbus_call(self._client.connect):
            _LOGGER.debug("Connect failed, pymodbus will retry")

    async def close(self):
        """Close connection"""
        _LOGGER.debug("Closing connection to modbus")
        await self._async_pymodbus_call(self._client.close)

    async def read_registers(self, start_address, num_registers, slave):
        """Read registers"""
        _LOGGER.debug("Reading register: (%d, %d, %d)", start_address, num_registers, slave)
        response = await self._async_pymodbus_call(
            self._client.read_input_registers,
            start_address,
            num_registers,
            slave,
        )

        if response.isError():
            raise ModbusIOException(f"Error reading registers: {response}")
        # convert to signed integers
        regs = [reading if reading < 32768 else reading - 65536 for reading in response.registers]
        return regs

    async def write_registers(self, address, values, slave):
        """Write registers"""
        _LOGGER.debug("Writing register: (%d, %s, %d)", address, values, slave)
        try:
            if len(values) > 1:
                values = [int(i) for i in values]
                response = await self._async_pymodbus_call(
                    self._client.write_registers,
                    address,
                    values,
                    slave,
                )
            else:
                response = await self._async_pymodbus_call(
                    self._client.write_register,
                    address,
                    int(values[0]),
                    slave,
                )
            if response.isError():
                self._write_errors += 1
                _LOGGER.warning(
                    "Error writing holding register - retry (%d/%d): %s",
                    self._write_errors,
                    _WRITE_ATTEMPTS,
                    response,
                )
                return await self._handle_write_error(address, values, slave)
            else:
                _LOGGER.debug("Sucessful write to holding register: %s", response)
                self._write_errors = 0
                return True

        except ModbusException as ex:
            self._write_errors += 1
            _LOGGER.warning(
                "Exception writing holding register - retry (%d/%d): %s",
                self._write_errors,
                _WRITE_ATTEMPTS,
                ex,
            )
            return await self._handle_write_error(address, values, slave)

    async def _handle_write_error(self, address, values, slave):
        """Handle a write error"""
        if self._write_errors >= _WRITE_ATTEMPTS:
            _LOGGER.error("No more retries left, giving up")
            self._write_errors = 0
            return False
        else:
            await asyncio.sleep(_WRITE_ERROR_SLEEP)
            await self.write_registers(address, values, slave)

    async def _async_pymodbus_call(self, call, *args):
        """Convert async to sync pymodbus call."""
        async with self._lock:
            return await self._hass.async_add_executor_job(call, *args)
