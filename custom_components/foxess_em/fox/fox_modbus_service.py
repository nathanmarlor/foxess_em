"""Fox controller"""

from datetime import datetime, time
import logging

from homeassistant.core import HomeAssistant

from .fox_modbus import FoxModbus
from .fox_service import FoxService

_LOGGER = logging.getLogger(__name__)
_DAY = 40002
_CHARGE_CURRENT = 41007
_MIN_SOC = 41011
_P1_ENABLE = 41001


class FoxModbuservice(FoxService):
    """Fox Cloud service"""

    def __init__(
        self,
        hass: HomeAssistant,
        modbus: FoxModbus,
        slave: int,
        off_peak_start: time,
        off_peak_end: time,
        user_min_soc: int = 10,
    ) -> None:
        """Init Fox Cloud service"""
        self._hass = hass
        self._modbus = modbus
        self._slave = slave
        self._off_peak_start = off_peak_start
        self._off_peak_end = off_peak_end
        self._user_min_soc = user_min_soc

    async def start_force_charge_now(self, *args) -> None:
        """Start force charge now"""
        now = datetime.now().astimezone()
        start = now.replace(hour=0, minute=1).time()
        stop = now.replace(hour=23, minute=59).time()

        await self._start_force_charge(start, stop)

    async def start_force_charge_off_peak(self, *args) -> None:
        """Start force charge off peak"""
        await self._start_force_charge(self._off_peak_start, self._off_peak_end)

    async def _start_force_charge(self, start, stop) -> None:
        """Start force charge"""
        _LOGGER.debug("Requesting start force charge from Fox Modbus")
        start_encoded = self._encode_time(start)
        stop_encoded = self._encode_time(stop)
        midnight_encoded = self._encode_time(time(hour=23, minute=59))
        next_day_encoded = self._encode_time(time(hour=0, minute=1))

        if start > stop:
            _LOGGER.debug("Setting double charge window - %s / %s", start, stop)
            await self._modbus.write_registers(
                _P1_ENABLE,
                [1, start_encoded, midnight_encoded, 1, next_day_encoded, stop_encoded],
                self._slave,
            )
        else:
            _LOGGER.debug("Setting single charge window - %s / %s", start, stop)
            await self._modbus.write_registers(
                _P1_ENABLE, [1, start_encoded, stop_encoded, 0, 0, 0], self._slave
            )

    async def stop_force_charge(self, *args) -> None:  # pylint: disable=unused-argument
        """Start force charge"""
        _LOGGER.debug("Requesting stop force charge from Fox Modbus")
        await self._modbus.write_registers(_P1_ENABLE, [0, 0, 0, 0, 0, 0], self._slave)

    async def set_min_soc(
        self, soc: int, *args
    ) -> None:  # pylint: disable=unused-argument
        """Start force charge"""
        _LOGGER.debug("Request set min SoC to Fox Modbus")
        await self._modbus.write_registers(_MIN_SOC, [soc], self._slave)

    async def set_charge_current(self, charge_current: float, *args) -> None:
        """Set charge current"""
        _LOGGER.debug(
            f"Requesting set charge current of {charge_current}A to Fox Modbus"
        )
        await self._modbus.write_registers(
            _CHARGE_CURRENT, [charge_current * 10], self._slave
        )

    async def device_info(self) -> None:
        """Get device info"""
        try:
            day = await self._modbus.read_registers(_DAY, 1, self._slave)
            return day[0] == datetime.now().day
        finally:
            await self._modbus.close()

    def _encode_time(self, core_time):
        """Encode time to Fox time"""
        return (core_time.hour * 256) + core_time.minute
