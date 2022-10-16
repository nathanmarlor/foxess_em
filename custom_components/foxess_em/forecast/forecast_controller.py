"""Forecast controller"""
import logging
from datetime import datetime

from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_utc_time_change
from pandas import DataFrame

from ..common.callback_controller import CallbackController
from ..common.unload_controller import UnloadController
from ..util.exceptions import NoDataError
from .forecast_model import ForecastModel
from .solcast_api import SolcastApiClient

_LOGGER = logging.getLogger(__name__)


class ForecastController(UnloadController, CallbackController):
    """Class to manage forecast retrieval"""

    def __init__(self, hass: HomeAssistant, api: SolcastApiClient) -> None:
        UnloadController.__init__(self)
        CallbackController.__init__(self)
        self._hass = hass
        self._api = ForecastModel(api)
        self._api_count = 0
        self._last_update = None

        for h in range(6, 20):
            forecast_update = async_track_utc_time_change(
                self._hass,
                self.async_refresh,
                hour=h,
                minute=0,
                second=0,
                local=True,
            )
            self._unload_listeners.append(forecast_update)

        # Reset # of API calls at midnight UTC
        reset_api = async_track_utc_time_change(
            self._hass,
            self._reset_api_count,
            hour=0,
            minute=0,
            second=10,
            local=False,
        )
        self._unload_listeners.append(reset_api)

    def ready(self) -> bool:
        """Model status"""
        return self._api.ready()

    async def async_refresh(self, *args) -> None:  # pylint: disable=unused-argument
        """Refresh forecast"""
        try:
            _LOGGER.debug("Refreshing forecast data")

            await self._api.refresh()

            self._api_count += 2
            self._last_update = datetime.now().astimezone()

            _LOGGER.debug("Finished refreshing forecast data, notifying listeners")
            self._notify_listeners()
        except NoDataError as ex:
            _LOGGER.warning(ex)
        except Exception as ex:
            _LOGGER.error(ex)

    def resample_data(self) -> DataFrame:
        """Return resampled data"""
        return self._api.resample_data()

    async def _reset_api_count(self, *args) -> None:  # pylint: disable=unused-argument
        """Reset API count to 0"""
        self._api_count = 0

    def total_kwh_forecast_today(self) -> float:
        """Total forecast today"""
        return self._api.total_kwh_forecast_today()

    def total_kwh_forecast_tomorrow(self) -> float:
        """Total forecast tomorrow"""
        return self._api.total_kwh_forecast_tomorrow()

    def total_kwh_forecast_today_remaining(self) -> float:
        """Return Remaining Forecasts data for today"""
        return self._api.total_kwh_forecast_today_remaining()

    def energy(self) -> DataFrame:
        """Return energy"""
        return self._api.energy()

    def last_update(self) -> datetime:
        """Return last update time"""
        return self._last_update

    def api_count(self) -> int:
        """Return API count"""
        return self._api_count
