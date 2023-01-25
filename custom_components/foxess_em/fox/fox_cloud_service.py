"""Fox controller"""
import logging
from datetime import datetime
from datetime import time

from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_call_later

from ..fox.fox_api import FoxApiClient
from ..util.exceptions import NoDataError

_BASE_URL = "https://www.foxesscloud.com/c/v0"
_SET_TIMES = "/device/battery/time/set"
_DEVICE = "/device/list"
_MIN_SOC = "/device/battery/soc/set"

_LOGGER = logging.getLogger(__name__)


class FoxCloudService:
    """Fox Cloud service"""

    def __init__(
        self,
        hass: HomeAssistant,
        api: FoxApiClient,
        off_peak_start: time,
        off_peak_end: time,
        user_min_soc: int = 11,
    ) -> None:
        """Init Fox Cloud service"""
        self._hass = hass
        self._api = api
        self._off_peak_start = off_peak_start
        self._off_peak_end = off_peak_end
        self._user_min_soc = user_min_soc
        self._device_sn = None

        if hass is not None:
            async_call_later(hass, 5, self.start_force_charge_off_peak)

    async def start_force_charge_now(self, *args) -> None:
        """Start force charge now"""
        now = datetime.now().astimezone()
        start = now.replace(hour=0, minute=1).time()
        stop = now.replace(hour=23, minute=59).time()

        device_sn = await self.device_serial_number()
        query = self._build_single_charge_query(device_sn, True, start, stop)

        await self._start_force_charge(query)

    async def start_force_charge_off_peak(self, *args) -> None:
        """Start force charge off peak"""
        device_sn = await self.device_serial_number()
        if self._off_peak_start > self._off_peak_end:
            # Off-peak period crosses midnight
            before_midnight = time(hour=23, minute=59)
            after_midnight = time(hour=0, minute=1)

            query = self._build_double_charge_query(
                device_sn,
                True,
                self._off_peak_start,
                before_midnight,
                after_midnight,
                self._off_peak_end,
            )
        else:

            query = self._build_single_charge_query(
                device_sn,
                True,
                self._off_peak_start,
                self._off_peak_end,
            )

        await self._start_force_charge(query)

    async def _start_force_charge(self, query: dict) -> None:
        """Start force charge"""
        _LOGGER.debug("Requesting start force charge from Fox Cloud")

        try:
            await self._api.async_post_data(
                f"{_BASE_URL}{_SET_TIMES}",
                query,
            )
        except NoDataError as ex:
            _LOGGER.error(ex)

    async def stop_force_charge(self, *args) -> None:  # pylint: disable=unused-argument
        """Start force charge"""
        _LOGGER.debug("Requesting stop force charge from Fox Cloud")

        try:
            device_sn = await self.device_serial_number()

            query = self._build_single_charge_query(
                device_sn,
                False,
                self._off_peak_start,
                self._off_peak_end,
            )

            await self._api.async_post_data(
                f"{_BASE_URL}{_SET_TIMES}",
                query,
            )
        except NoDataError as ex:
            _LOGGER.error(ex)

    async def set_min_soc(
        self, soc: int, *args
    ) -> None:  # pylint: disable=unused-argument
        """Start force charge"""
        _LOGGER.debug("Sending min SoC to Fox Cloud")

        try:
            device_sn = await self.device_serial_number()
            await self._api.async_post_data(
                f"{_BASE_URL}{_MIN_SOC}", self._build_min_soc_query(device_sn, soc)
            )
        except NoDataError as ex:
            _LOGGER.error(ex)

    async def device_serial_number(self) -> None:
        """Get device serial number"""
        if self._device_sn is None:
            device = await self._api.async_post_data(
                f"{_BASE_URL}{_DEVICE}", self._build_device_query()
            )
            self._device_sn = device["devices"][0]["deviceSN"]
            _LOGGER.debug(f"Retrieved Fox device serial number: {self._device_sn}")

        return self._device_sn

    def _build_device_query(self) -> dict:
        """Build device query object"""
        return {
            "pagesize": 10,
            "currentPage": 1,
            "total": 0,
            "condition": {"queryDate": {"begin": 0, "end": 0}},
        }

    def _build_min_soc_query(self, device_sn: str, soc: int) -> dict:
        """Build min SoC query object"""
        return {"sn": device_sn, "minGridSoc": soc, "minSoc": self._user_min_soc * 100}

    def _build_single_charge_query(
        self, device_sn: str, start_stop: bool, start_time: time, end_time: time
    ) -> dict:
        """Build device query object"""

        query = {
            "sn": device_sn,
            "times": [
                {
                    "tip": "",
                    "enableCharge": start_stop,
                    "enableGrid": start_stop,
                    "startTime": {
                        "hour": str(start_time.hour).zfill(2),
                        "minute": str(start_time.minute).zfill(2),
                    },
                    "endTime": {
                        "hour": str(end_time.hour).zfill(2),
                        "minute": str(end_time.minute).zfill(2),
                    },
                },
                {
                    "tip": "",
                    "enableCharge": False,
                    "enableGrid": False,
                    "startTime": {"hour": 0, "minute": 0},
                    "endTime": {"hour": 0, "minute": 0},
                },
            ],
        }

        return query

    def _build_double_charge_query(
        self,
        device_sn: str,
        start_stop: bool,
        first_start_time: time,
        first_end_time: time,
        second_start_time: time,
        second_end_time: time,
    ) -> dict:
        """Build device query object"""

        query = {
            "sn": device_sn,
            "times": [
                {
                    "tip": "",
                    "enableCharge": start_stop,
                    "enableGrid": start_stop,
                    "startTime": {
                        "hour": str(first_start_time.hour).zfill(2),
                        "minute": str(first_start_time.minute).zfill(2),
                    },
                    "endTime": {
                        "hour": str(first_end_time.hour).zfill(2),
                        "minute": str(first_end_time.minute).zfill(2),
                    },
                },
                {
                    "tip": "",
                    "enableCharge": start_stop,
                    "enableGrid": start_stop,
                    "startTime": {
                        "hour": str(second_start_time.hour).zfill(2),
                        "minute": str(second_start_time.minute).zfill(2),
                    },
                    "endTime": {
                        "hour": str(second_end_time.hour).zfill(2),
                        "minute": str(second_end_time.minute).zfill(2),
                    },
                },
            ],
        }

        return query
