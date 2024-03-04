"""Fox controller"""

from datetime import datetime, time
import logging

from homeassistant.core import HomeAssistant

from ..util.exceptions import NoDataError
from .fox_cloud_api import FoxCloudApiClient
from .fox_service import FoxService

_SET_TIMES = "/op/v0/device/battery/forceChargeTime/set"
_DEVICE = "/op/v0/device/list"
_MIN_SOC = "/op/v0/device/battery/soc/set"

_LOGGER = logging.getLogger(__name__)


class FoxCloudService(FoxService):
    """Fox Cloud service"""

    def __init__(
        self,
        hass: HomeAssistant,
        api: FoxCloudApiClient,
        off_peak_start: time,
        off_peak_end: time,
        user_min_soc: int = 10,
    ) -> None:
        """Init Fox Cloud service"""
        self._hass = hass
        self._api = api
        self._off_peak_start = off_peak_start
        self._off_peak_end = off_peak_end
        self._user_min_soc = user_min_soc
        self._device_info = None

    async def start_force_charge_now(self, *args) -> None:
        """Start force charge now"""
        now = datetime.now().astimezone()
        start = now.replace(hour=0, minute=1).time()
        stop = now.replace(hour=23, minute=59).time()

        device_info = await self.device_info()
        device_sn = device_info["deviceSN"]
        query = self._build_start_single_charge_query(device_sn, start, stop)

        await self._start_force_charge(query)

    async def start_force_charge_off_peak(self, *args) -> None:
        """Start force charge off peak"""
        device_info = await self.device_info()
        device_sn = device_info["deviceSN"]
        if self._off_peak_start > self._off_peak_end:
            # Off-peak period crosses midnight

            query = self._build_start_double_charge_query(
                device_sn,
                self._off_peak_start,
                self._off_peak_end,
            )
        else:
            query = self._build_start_single_charge_query(
                device_sn,
                self._off_peak_start,
                self._off_peak_end,
            )

        await self._start_force_charge(query)

    async def _start_force_charge(self, query: dict) -> None:
        """Start force charge"""
        _LOGGER.debug("Requesting start force charge from Fox Cloud")

        try:
            await self._api.async_post_data(_SET_TIMES, query)
        except NoDataError as ex:
            _LOGGER.error(ex)

    async def stop_force_charge(self, *args) -> None:  # pylint: disable=unused-argument
        """Start force charge"""
        _LOGGER.debug("Requesting stop force charge from Fox Cloud")

        try:
            device_info = await self.device_info()
            device_sn = device_info["deviceSN"]

            query = self._build_stop_charge_query(device_sn)

            await self._api.async_post_data(_SET_TIMES, query)
        except NoDataError as ex:
            _LOGGER.error(ex)

    async def set_min_soc(
        self, soc: int, *args
    ) -> None:  # pylint: disable=unused-argument
        """Start force charge"""
        _LOGGER.debug("Sending min SoC to Fox Cloud")

        try:
            device_info = await self.device_info()
            device_sn = device_info["deviceSN"]
            await self._api.async_post_data(
                _MIN_SOC, self._build_min_soc_query(device_sn, soc)
            )
        except NoDataError as ex:
            _LOGGER.error(ex)

    async def set_charge_current(self, charge_current: float, *args) -> None:
        """Set charge current"""
        _LOGGER.debug(
            "Skipping call to set charge current as not supported using the Cloud"
        )

    async def device_info(self) -> None:
        """Get device serial number"""
        if self._device_info is None:
            device = await self._api.async_post_data(
                _DEVICE, self._build_device_query()
            )
            self._device_info = device["data"][0]
            _LOGGER.debug(f"Retrieved Fox device info: {self._device_info}")

        return self._device_info

    def _build_device_query(self) -> dict:
        """Build device query object"""
        return {
            "pageSize": 10,
            "currentPage": 1,
        }

    def _build_min_soc_query(self, device_sn: str, soc: int) -> dict:
        """Build min SoC query object"""
        return {
            "sn": device_sn,
            "minSocOnGrid": soc,
            "minSoc": int(self._user_min_soc * 100),
        }

    def _build_stop_charge_query(self, device_sn: str) -> dict:
        """Build stop charge query"""

        query = {
            "sn": device_sn,
            "enable1": False,
            "enable2": False,
            "startTime1": {
                "hour": 0,
                "minute": 0,
            },
            "endTime1": {
                "hour": 0,
                "minute": 0,
            },
            "startTime2": {
                "hour": 0,
                "minute": 0,
            },
            "endTime2": {
                "hour": 0,
                "minute": 0,
            },
        }

        return query

    def _build_start_single_charge_query(
        self, device_sn: str, start_time: time, end_time: time
    ) -> dict:
        """Build single time charge query"""

        query = {
            "sn": device_sn,
            "enable1": True,
            "enable2": False,
            "startTime1": {
                "hour": start_time.hour,
                "minute": start_time.minute,
            },
            "endTime1": {
                "hour": end_time.hour,
                "minute": end_time.minute,
            },
            "startTime2": {
                "hour": 0,
                "minute": 0,
            },
            "endTime2": {
                "hour": 0,
                "minute": 0,
            },
        }

        return query

    def _build_start_double_charge_query(
        self,
        device_sn: str,
        start_time: time,
        stop_time: time,
    ) -> dict:
        """Build double time charge query"""

        before_midnight = time(hour=23, minute=59)
        after_midnight = time(hour=0, minute=1)

        query = {
            "sn": device_sn,
            "enable1": True,
            "enable2": True,
            "startTime1": {
                "hour": start_time.hour,
                "minute": start_time.minute,
            },
            "endTime1": {
                "hour": before_midnight.hour,
                "minute": before_midnight.minute,
            },
            "startTime2": {
                "hour": after_midnight.hour,
                "minute": after_midnight.minute,
            },
            "endTime2": {
                "hour": stop_time.hour,
                "minute": stop_time.minute,
            },
        }

        return query
