"""Fox controller"""
import logging
from datetime import datetime

from ..fox.fox_api import FoxApiClient
from ..util.exceptions import NoDataError

_BASE_URL = "https://www.foxesscloud.com/c/v0"
_SET_TIMES = "/device/battery/time/set"
_DEVICE = "/device/list"

_LOGGER = logging.getLogger(__name__)


class FoxCloudService:
    """Fox Cloud service"""

    def __init__(self, api: FoxApiClient) -> None:
        """Init Fox Cloud service"""
        self._api = api
        self._device_sn = None

    async def start_force_charge(self, *args):
        """Start force charge"""
        _LOGGER.debug("Requesting start force charge from Fox Cloud")

        try:
            device_sn = await self.device_serial_number()
            await self._api.async_post_data(
                f"{_BASE_URL}{_SET_TIMES}", self._build_charge_start_query(device_sn)
            )
        except NoDataError as ex:
            _LOGGER.error(ex)

    async def stop_force_charge(self, *args):
        """Start force charge"""
        _LOGGER.debug("Requesting stop force charge from Fox Cloud")

        try:
            device_sn = await self.device_serial_number()
            await self._api.async_post_data(
                f"{_BASE_URL}{_SET_TIMES}", self._build_charge_stop_query(device_sn)
            )
        except NoDataError as ex:
            _LOGGER.error(ex)

    async def device_serial_number(self):
        """Get device serial number"""
        if self._device_sn is None:
            device = await self._api.async_post_data(
                f"{_BASE_URL}{_DEVICE}", self._build_device_query()
            )
            self._device_sn = device["devices"][0]["deviceSN"]
            _LOGGER.debug(f"Retrieved Fox device serial number: {self._device_sn}")

        return self._device_sn

    def _build_device_query(self):
        """Build device query object"""
        return {
            "pagesize": 10,
            "currentPage": 1,
            "total": 0,
            "condition": {"queryDate": {"begin": 0, "end": 0}},
        }

    def _build_charge_start_query(self, device_sn: str):
        """Build device query object"""
        now = datetime.now().astimezone()
        midnight = now.replace(hour=23, minute=59, second=59, microsecond=0)

        query = {
            "sn": device_sn,
            "times": [
                {
                    "tip": "",
                    "enableCharge": True,
                    "enableGrid": True,
                    "startTime": {
                        "hour": str(now.hour).zfill(2),
                        "minute": str(now.minute).zfill(2),
                    },
                    "endTime": {
                        "hour": str(midnight.hour).zfill(2),
                        "minute": str(midnight.minute).zfill(2),
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

    def _build_charge_stop_query(self, device_sn: str):
        """Build device query object"""
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
