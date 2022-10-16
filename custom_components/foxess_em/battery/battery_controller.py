"""Battery controller"""
import logging
from datetime import datetime
from datetime import time

from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_state_change

from ..average.average_controller import AverageController
from ..common.callback_controller import CallbackController
from ..common.unload_controller import UnloadController
from ..forecast.forecast_controller import ForecastController
from ..util.exceptions import NoDataError
from .battery_model import BatteryModel

_LOGGER = logging.getLogger(__name__)
_BOOST = 1


class BatteryController(UnloadController, CallbackController):
    """Battery controller"""

    def __init__(
        self,
        hass: HomeAssistant,
        forecast_controller: ForecastController,
        average_controller: AverageController,
        min_soc: float,
        capacity: float,
        dawn_buffer: float,
        day_buffer: float,
        charge_rate: float,
        eco_start_time: time,
        eco_end_time: time,
        battery_soc: str,
    ) -> None:
        UnloadController.__init__(self)
        CallbackController.__init__(self)
        self._hass = hass
        self._model = BatteryModel(
            hass,
            min_soc,
            capacity,
            dawn_buffer,
            day_buffer,
            charge_rate,
            eco_start_time,
            eco_end_time,
            battery_soc,
        )
        self._forecast_controller = forecast_controller
        self._average_controller = average_controller
        self._last_update = None
        self._boost = False
        self._full = False

        # Refresh on SoC change
        battery_refresh = async_track_state_change(
            self._hass, battery_soc, self.refresh
        )
        self._unload_listeners.append(battery_refresh)

    def ready(self) -> bool:
        """Model status"""
        return self._model.ready()

    async def async_refresh(self) -> None:
        """Async refresh"""
        self.refresh()

    def refresh(self, *args) -> None:  # pylint: disable=unused-argument
        """Refresh battery model"""
        _LOGGER.debug("Refreshing battery model")

        try:
            load = self._average_controller.resample_data()
            forecast = self._forecast_controller.resample_data()
            self._model.refresh_battery_model(forecast, load)

            self._last_update = datetime.now().astimezone()

            _LOGGER.debug("Finished refreshing battery model, notifying listeners")
            self._notify_listeners()
        except NoDataError as ex:
            _LOGGER.warning(ex)
        except Exception as ex:
            _LOGGER.error(ex)

    def update_callback(self) -> None:
        """Schedule a refresh"""
        self.refresh()

    def charge_to_perc(self) -> int:
        """Calculate percentage target"""
        return self._model.charge_to_perc(self.charge_total() + self.state_at_eco_end())

    def state_at_dawn(self) -> float:
        """Battery state at dawn"""
        battery_value = self._model.state_at_dawn()
        return round(battery_value, 2)

    def state_at_eco_end(self) -> float:
        """Battery state at end of eco period"""
        battery_value = self._model.state_at_eco_end()
        return round(battery_value, 2)

    def state_at_eco_start(self) -> float:
        """Battery state at start of eco period"""
        battery_value = self._model.state_at_eco_start()
        return round(battery_value, 2)

    def todays_dawn_time(self) -> datetime:
        """Return todays dawn time"""
        return self._model.todays_dawn_time()

    def todays_dawn_time_str(self) -> str:
        """Return todays dawn time in ISO format"""
        return self._model.todays_dawn_time().isoformat()

    def next_dawn_time(self) -> datetime:
        """Return next dawn time"""
        return self._model.next_dawn_time()

    def dawn_charge_needs(self) -> float:
        """Dawn charge needs"""
        return self._model.dawn_charge_needs()

    def day_charge_needs(self) -> float:
        """Day charge needs"""
        state_at_eco_end = self.state_at_eco_end()
        house_load = self._average_controller.average_peak_house_load()
        forecast_today = self._forecast_controller.total_kwh_forecast_today()
        forecast_tomorrow = self._forecast_controller.total_kwh_forecast_tomorrow()

        return self._model.day_charge_needs(
            forecast_today, forecast_tomorrow, state_at_eco_end, house_load
        )

    def charge_total(self) -> float:
        """Total kWh required to charge"""
        if self._full:
            return self._model.ceiling_charge_total(float("inf"))

        dawn_charge = self.dawn_charge_needs()
        day_charge = self.day_charge_needs()

        total = max([dawn_charge, day_charge])

        if self._boost:
            total += _BOOST
            total = self._model.ceiling_charge_total(total)

        return total

    def charge_start_time(self) -> datetime:
        """Return charge time"""
        return self._model.charge_start_time(self.charge_total())

    def charge_start_time_str(self) -> str:
        """Return charge time in ISO format"""
        return self.charge_start_time().isoformat()

    def battery_last_update(self) -> datetime:
        """Battery last update"""
        return self._last_update

    def battery_last_update_str(self) -> str:
        """Battery last update in ISO format"""
        return self.battery_last_update().isoformat()

    def average_last_update_str(self) -> str:
        """Average last update in ISO format"""
        return self._average_controller.last_update().isoformat()

    def forecast_last_update_str(self) -> str:
        """Forecast last update in ISO format"""
        return self._forecast_controller.last_update().isoformat()

    def set_boost(self, status: bool) -> None:
        """Set boost on/off"""
        self._boost = status
        self._notify_listeners()

    def boost_status(self) -> bool:
        """Boost status"""
        return self._boost

    def set_full(self, status: bool) -> None:
        """Set full charge on/off"""
        self._full = status
        self._notify_listeners()

    def full_status(self) -> bool:
        """Full status"""
        return self._full
