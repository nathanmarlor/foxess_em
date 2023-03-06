"""Fox controller"""
import logging
from datetime import datetime
from datetime import time

from homeassistant.core import HomeAssistant

from ..util.exceptions import NoDataError
from .fox_cloud_api import FoxCloudApiClient
from .fox_service import FoxService

_BASE_URL = "https://www.foxesscloud.com/c/v0"
_SET_TIMES = "/device/battery/time/set"
_DEVICE = "/device/list"
_MIN_SOC = "/device/battery/soc/set"
_SETTINGS = "/device/setting/set"

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
            device_info = await self.device_info()
            device_sn = device_info["deviceSN"]

            query = self._build_stop_charge_query(device_sn)

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
            device_info = await self.device_info()
            device_sn = device_info["deviceSN"]
            await self._api.async_post_data(
                f"{_BASE_URL}{_MIN_SOC}", self._build_min_soc_query(device_sn, soc)
            )
        except NoDataError as ex:
            _LOGGER.error(ex)

    async def set_charge_current(self, charge_current: float, *args) -> None:
        """Set charge current"""
        _LOGGER.debug(f"Sending charge current of {charge_current}A to Fox Cloud")

        try:
            device_info = await self.device_info()
            device_id = device_info["deviceID"]
            await self._api.async_post_data(
                f"{_BASE_URL}{_SETTINGS}",
                self._build_charge_query(device_id, charge_current),
            )
        except NoDataError as ex:
            _LOGGER.error(ex)

    async def device_info(self) -> None:
        """Get device serial number"""
        if self._device_info is None:
            device = await self._api.async_post_data(
                f"{_BASE_URL}{_DEVICE}", self._build_device_query()
            )
            self._device_info = device["devices"][0]
            _LOGGER.debug(f"Retrieved Fox device info: {self._device_info}")

        return self._device_info

    def _build_device_query(self) -> dict:
        """Build device query object"""
        return {
            "pagesize": 10,
            "currentPage": 1,
            "total": 0,
            "condition": {"queryDate": {"begin": 0, "end": 0}},
        }

    def _build_charge_query(self, device_id: str, charge_current: float) -> dict:
        """Build device charge object"""
        return {
            "id": device_id,
            "key": "h112__basic2__00",
            "values": {"h112__basic2__00": str(charge_current)},
        }

    def _build_min_soc_query(self, device_sn: str, soc: int) -> dict:
        """Build min SoC query object"""
        return {"sn": device_sn, "minGridSoc": soc, "minSoc": self._user_min_soc * 100}

    def _build_stop_charge_query(self, device_sn: str) -> dict:
        """Build stop charge query"""

        query = {
            "sn": device_sn,
            "times": [
                {
                    "tip": "",
                    "enableCharge": False,
                    "enableGrid": False,
                    "startTime": {"hour": 0, "minute": 0},
                    "endTime": {"hour": 0, "minute": 0},
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

    def _build_start_single_charge_query(
        self, device_sn: str, start_time: time, end_time: time
    ) -> dict:
        """Build single time charge query"""

        query = {
            "sn": device_sn,
            "times": [
                {
                    "tip": "",
                    "enableCharge": True,
                    "enableGrid": True,
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
            "times": [
                {
                    "tip": "",
                    "enableCharge": True,
                    "enableGrid": True,
                    "startTime": {
                        "hour": str(start_time.hour).zfill(2),
                        "minute": str(start_time.minute).zfill(2),
                    },
                    "endTime": {
                        "hour": str(before_midnight.hour).zfill(2),
                        "minute": str(before_midnight.minute).zfill(2),
                    },
                },
                {
                    "tip": "",
                    "enableCharge": True,
                    "enableGrid": True,
                    "startTime": {
                        "hour": str(after_midnight.hour).zfill(2),
                        "minute": str(after_midnight.minute).zfill(2),
                    },
                    "endTime": {
                        "hour": str(stop_time.hour).zfill(2),
                        "minute": str(stop_time.minute).zfill(2),
                    },
                },
            ],
        }

        return query
