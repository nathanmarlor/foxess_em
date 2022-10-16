"""Average controller"""
import logging
from datetime import datetime
from datetime import time
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_utc_time_change
from pandas import DataFrame

from ..average.average_model import AverageModel
from ..common.callback_controller import CallbackController
from ..common.unload_controller import UnloadController
from .tracked_sensor import HistorySensor
from .tracked_sensor import TrackedSensor

_LOGGER = logging.getLogger(__name__)


class AverageController(UnloadController, CallbackController):
    """Class to manage history retrieval"""

    def __init__(
        self,
        hass: HomeAssistant,
        eco_start_time: time,
        eco_end_time: time,
        house_power: str,
        aux_power: list[str],
    ) -> None:
        UnloadController.__init__(self)
        CallbackController.__init__(self)
        self._hass = hass
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

    def ready(self) -> bool:
        """Model status"""
        return self._model.ready()

    async def async_refresh(
        self, *args, sensor_id: str = None
    ) -> None:  # pylint: disable=unused-argument
        """Refresh data"""

        await self._model.refresh(sensor_id)

        if sensor_id is None:
            _LOGGER.debug("Finished refreshing averages model, notifying listeners")
            self._last_update = datetime.now().astimezone()
            self._notify_listeners()

    def resample_data(self) -> DataFrame:
        """Return resampled data"""
        return self._model.resample_data()

    def average_all_house_load(self) -> float:
        """Average daily house load"""
        return self._model.average_all_house_load()

    def average_peak_house_load(self) -> float:
        """Average peak house load"""
        return self._model.average_peak_house_load()

    def house_load_15m(self) -> float:
        """Calculate 15m house load"""
        return self._model.average_house_load_15m()

    def last_update(self) -> datetime:
        """Return last update"""
        return self._last_update
