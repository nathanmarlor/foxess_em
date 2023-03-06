import logging

from pymodbus.client import ModbusTcpClient

_LOGGER = logging.getLogger(__name__)
_SLAVE = 247


class FoxModbus:
    """Modbus"""

    def __init__(self, host, port=502):
        """Init"""
        self._host = host
        self._port = port
        self._client = ModbusTcpClient(self._host, self._port)

    def _connect(self):
        """Connect to device"""
        if not self._client.connect():
            raise ConnectionError(
                f"Error connecting to device: ({self._host}:{self._port})"
            )

    def read_input_registers(self, start_address, num_registers):
        """Read registers"""
        if not self._client.is_socket_open():
            _LOGGER.info(f"Connecting to modbus: ({self._host}:{self._port})")
            self._connect()

        _LOGGER.info(f"Reading input register: ({start_address}, {num_registers})")

        response = self._client.read_input_registers(
            start_address, num_registers, _SLAVE
        )
        if response.isError():
            raise ConnectionError(f"Error reading input registers: {response}")
        return response.registers

    def write_registers(self, register_address, register_values):
        """Write registers"""
        if not self._client.is_socket_open():
            _LOGGER.info(f"Connecting to modbus: ({self._host}:{self._port})")
            self._connect()

        _LOGGER.info(f"Writing register: ({register_address}, {register_values})")

        if len(register_values) > 1:
            response = self._client.write_registers(
                register_address, register_values, _SLAVE
            )
        else:
            response = self._client.write_register(
                register_address, register_values[0], _SLAVE
            )
        if response.isError():
            raise ConnectionError(f"Error writing holding register: {response}")
        return True
