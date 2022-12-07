"""Average controller"""
import logging
from datetime import datetime
from datetime import time
from datetime import timedelta

from custom_components.foxess_em.common.hass_load_controller import HassLoadController
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_utc_time_change
from pandas import DataFrame

from ..average.average_model import AverageModel
from ..common.callback_controller import CallbackController
from ..common.unload_controller import UnloadController
from .tracked_sensor import HistorySensor
from .tracked_sensor import TrackedSensor

_LOGGER = logging.getLogger(__name__)


class AverageController(UnloadController, CallbackController, HassLoadController):
    """Class to manage history retrieval"""

    def __init__(
        self,
        hass: HomeAssistant,
        eco_start_time: time,
        eco_end_time: time,
        house_power: str,
        aux_power: list[str],
    ) -> None:
        self._hass = hass
        self._last_update = None

        entities = {
            "house_load_7d": TrackedSensor(
                HistorySensor(house_power, timedelta(days=2), False),
                [
                    HistorySensor(sensor, timedelta(days=2), False)
                    for sensor in aux_power
                ],
            )
        }

        self._model = AverageModel(hass, entities, eco_start_time, eco_end_time)

        # Setup mixins
        UnloadController.__init__(self)
        CallbackController.__init__(self)
        HassLoadController.__init__(self, hass, self.async_refresh)

        # Refresh every hour on the half hour
        midnight_refresh = async_track_utc_time_change(
            self._hass,
            self.async_refresh,
            minute=30,
            second=0,
            local=True,
        )
        self._unload_listeners.append(midnight_refresh)

    def ready(self) -> bool:
        """Model status"""
        return self._model.ready()

    async def async_refresh(self, *args) -> None:  # pylint: disable=unused-argument
        """Refresh data"""
        _LOGGER.debug("Refreshing averages model")

        await self._model.refresh()
        self._last_update = datetime.now().astimezone()

        _LOGGER.debug("Finished refreshing averages model, notifying listeners")
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

    def last_update(self) -> datetime:
        """Return last update"""
        return self._last_update
