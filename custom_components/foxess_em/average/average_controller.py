import logging
from datetime import datetime
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_utc_time_change

from ..average.average_model import AverageModel
from ..common.callback_controller import CallbackController
from ..common.unload_controller import UnloadController
from ..forecast.forecast_controller import ForecastController
from .tracked_sensor import HistorySensor
from .tracked_sensor import TrackedSensor

_LOGGER = logging.getLogger(__name__)


class AverageController(UnloadController, CallbackController):
    """Class to manage history retrieval"""

    def __init__(
        self,
        hass: HomeAssistant,
        forecast_controller: ForecastController,
        eco_start_time,
        eco_end_time,
        house_power,
        aux_power,
    ) -> None:
        UnloadController.__init__(self)
        CallbackController.__init__(self)
        self._hass = hass
        self._forecast_controller = forecast_controller
        self._last_update = None

        entities = {
            "house_load_7d": TrackedSensor(
                HistorySensor(house_power, timedelta(days=2), True),
                [
                    HistorySensor(sensor, timedelta(days=2), True)
                    for sensor in aux_power
                ],
            ),
            "house_load_15m": TrackedSensor(
                HistorySensor(house_power, timedelta(minutes=15)), []
            ),
        }

        self._model = AverageModel(hass, entities, eco_start_time, eco_end_time)

        # Refresh at midnight
        midnight_refresh = async_track_utc_time_change(
            self._hass,
            self.async_refresh,
            hour=0,
            minute=0,
            second=10,
            local=True,
        )
        self._unload_listeners.append(midnight_refresh)

    def ready(self):
        """Model status"""
        return self._model.ready()

    async def async_refresh(self, *args, sensor_id=None):
        """Refresh data"""

        await self._model.refresh(sensor_id)

        if sensor_id is None:
            _LOGGER.debug("Finished refreshing averages model, notifying listeners")
            self._last_update = datetime.now().astimezone()
            self._notify_listeners()

    def resample_data(self):
        """Return resampled data"""
        return self._model.resample_data()

    def average_all_house_load(self):
        """Average daily house load"""
        return self._model.average_all_house_load()

    def average_peak_house_load(self):
        """Average peak house load"""
        return self._model.average_peak_house_load()

    def house_load_15m(self):
        """Calculate 15m house load"""
        return self._model.average_house_load_15m()

    def last_update(self):
        """Return last update"""
        return self._last_update
