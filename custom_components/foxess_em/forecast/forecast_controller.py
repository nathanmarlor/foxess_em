"""Forecast controller"""
import logging
from datetime import datetime
from datetime import time
from datetime import timedelta

from custom_components.foxess_em.common.hass_load_controller import HassLoadController
from custom_components.foxess_em.const import FORECAST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_utc_time_change
from pandas import DataFrame

from ..common.callback_controller import CallbackController
from ..common.unload_controller import UnloadController
from ..util.exceptions import NoDataError
from .forecast_model import ForecastModel
from .solcast_api import SolcastApiClient

_LOGGER = logging.getLogger(__name__)
_CALLS = 2
_API_BUFFER = _CALLS * 2
_START_HOUR = 6
_HOURS = 12


class ForecastController(UnloadController, CallbackController, HassLoadController):
    """Class to manage forecast retrieval"""

    def __init__(self, hass: HomeAssistant, api: SolcastApiClient) -> None:
        self._hass = hass
        self._api = ForecastModel(api)
        self._api_count = 0
        self._api_limit = 50
        self._last_update = None
        self._refresh_listeners = []

        # Setup mixins
        UnloadController.__init__(self)
        CallbackController.__init__(self)
        HassLoadController.__init__(self, hass, self.load)

        self._setup_reset()

    async def load(self, *args) -> None:
        """Load forecast from state"""
        raw_data = self._hass.states.get(FORECAST)

        if raw_data is not None and all(
            k in raw_data.attributes for k in ("forecast", "last_update")
        ):
            last_update = datetime.fromisoformat(raw_data.attributes["last_update"])
            cache_age = datetime.now().astimezone() - last_update
            _LOGGER.debug("Forecast cache is %s old", cache_age)
            if cache_age < timedelta(days=1):
                _LOGGER.debug("Loading forecast data from cache")
                forecast_data = raw_data.attributes["forecast"]
                self._api.load(forecast_data)
                self._last_update = last_update
                _LOGGER.debug(
                    "Finished loading forecast data from cache, notifying listeners"
                )
                await self._async_get_site_info()
                self._notify_listeners()
            else:
                await self.async_refresh()
        else:
            await self.async_refresh()

    async def _setup_refresh(self, *args):
        """Setup refresh intervals"""

        self._clear_listeners()

        now = datetime.now().astimezone()
        default_start = now.replace(hour=_START_HOUR, minute=0, second=0, microsecond=0)
        default_end = default_start + timedelta(hours=_HOURS)
        actual_start = max(now, default_start)

        sites = await self._api.sites()

        sites = len(sites["sites"])
        _LOGGER.debug(f"Creating refresh schedule for {sites} sites")

        api_available = int(
            (self._api_limit - self._api_count - _API_BUFFER) / (_CALLS * sites)
        )
        _LOGGER.debug(f"Calculated {api_available} available refreshes")

        self._add_refresh(
            now.replace(hour=_START_HOUR, minute=0, second=0, microsecond=0).time()
        )

        # default first refresh is used
        if now < default_start:
            api_available -= 1

        # no api calls left or somehow landed after the final refresh
        if api_available < 1 or now > default_end:
            return

        minutes_diff = int((default_end - actual_start).seconds / 60)
        interval = int(minutes_diff / api_available)
        for i in range(1, api_available + 1):
            update_time = (actual_start + timedelta(minutes=interval * i)).time()
            self._add_refresh(update_time)

    def _clear_listeners(self):
        """Clear all listeners"""
        _LOGGER.debug(f"Clearing {len(self._refresh_listeners)} refresh listeners")
        for listener in self._refresh_listeners:
            listener()
            # Remove any dangling references in unload listeners
            if listener in self._unload_listeners:
                self._unload_listeners.remove(listener)
        self._refresh_listeners.clear()

    def _add_refresh(self, refresh_time: time) -> None:
        """Add a forecast refresh"""
        _LOGGER.debug(f"Setting up forecast refresh at {refresh_time}")

        forecast_update = async_track_utc_time_change(
            self._hass,
            self.async_refresh,
            hour=refresh_time.hour,
            minute=refresh_time.minute,
            second=0,
            local=True,
        )
        self._refresh_listeners.append(forecast_update)
        self._unload_listeners.append(forecast_update)

    def _setup_reset(self, *args) -> None:
        """Setup refresh intervals"""
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
            self._last_update = datetime.now().astimezone()

            _LOGGER.debug("Finished refreshing forecast data")
        except NoDataError as ex:
            _LOGGER.warning(ex)
        except Exception as ex:
            _LOGGER.error(f"{ex!r}")

        await self._async_get_site_info()
        self._notify_listeners()

    async def _async_get_site_info(
        self, *args
    ) -> None:  # pylint: disable=unused-argument
        """Refresh site info"""
        try:
            _LOGGER.debug("Refreshing Solcast site info")

            api_status = await self._api.api_status()
            self._api_count = api_status["daily_limit_consumed"]
            self._api_limit = api_status["daily_limit"]
            await self._setup_refresh()

            _LOGGER.debug("Finished refreshing Solcast site info")
        except Exception as ex:
            _LOGGER.error(f"{ex!r}")

    def resample_data(self) -> DataFrame:
        """Return resampled data"""
        return self._api.resample_data()

    def raw_data(self) -> list:
        """Return resampled data"""
        return self._api.raw_data()

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

    def empty(self) -> int:
        """Hack for hidden sensors"""
        return 0
