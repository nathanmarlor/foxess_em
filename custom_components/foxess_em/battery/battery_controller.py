"""Battery controller"""

from datetime import datetime, time
import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_state_change_event

from custom_components.foxess_em.battery.battery_util import BatteryUtils
from custom_components.foxess_em.battery.schedule import Schedule
from custom_components.foxess_em.common.hass_load_controller import HassLoadController
from custom_components.foxess_em.util.peak_period_util import PeakPeriodUtils

from ..average.average_controller import AverageController
from ..common.callback_controller import CallbackController
from ..common.unload_controller import UnloadController
from ..forecast.forecast_controller import ForecastController
from ..util.exceptions import NoDataError
from .battery_model import BatteryModel

_LOGGER = logging.getLogger(__name__)


class BatteryController(UnloadController, CallbackController, HassLoadController):
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
        eco_start_time: time,
        battery_soc: str,
        schedule: Schedule,
        peak_utils: PeakPeriodUtils,
    ) -> None:
        self._hass = hass
        self._schedule = schedule
        self._peak_utils = peak_utils
        self._capacity = capacity
        self._battery_utils = BatteryUtils(capacity, min_soc)
        self._model = BatteryModel(
            hass,
            min_soc,
            capacity,
            dawn_buffer,
            day_buffer,
            eco_start_time,
            battery_soc,
            schedule,
            peak_utils,
            self._battery_utils,
        )
        self._forecast_controller = forecast_controller
        self._average_controller = average_controller
        self._last_update = None

        # Setup mixins
        UnloadController.__init__(self)
        CallbackController.__init__(self)
        HassLoadController.__init__(self, hass, self.async_refresh)

        # Refresh on SoC change
        battery_refresh = async_track_state_change_event(
            self._hass, battery_soc, self.refresh
        )
        self._unload_listeners.append(battery_refresh)

    def ready(self) -> bool:
        """Model status"""
        return self._model.ready()

    async def async_refresh(self, *args) -> None:
        """Async refresh"""
        self.refresh()

    def refresh(self, *args) -> None:  # pylint: disable=unused-argument
        """Refresh battery model"""
        _LOGGER.debug("Refreshing battery model")

        if not (self._average_controller.ready() and self._forecast_controller.ready()):
            return

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
            _LOGGER.error(f"{ex!r}")

    def update_callback(self) -> None:
        """Schedule a refresh"""
        self.refresh()

    def charge_to_perc(self) -> int:
        """Calculate percentage target"""
        return self._battery_utils.charge_to_perc(self.min_soc())

    def get_schedule(self, start: datetime = None, end: datetime = None):
        """Return charge schedule"""
        schedule = self._schedule.get_all()

        if start is None or end is None:
            return schedule

        return {
            k: v
            for k, v in schedule.items()
            if datetime.fromisoformat(k) > start and datetime.fromisoformat(k) < end
        }

    def raw_data(self):
        """Return raw data in dictionary form"""
        return self._model.raw_data()

    def state_at_eco_start(self) -> float:
        """Battery state at start of eco period"""
        return round(self._schedule_info()["battery"], 2)

    def dawn_charge_needs(self) -> float:
        """Dawn charge needs"""
        return self._schedule_info()["dawn"]

    def day_charge_needs(self) -> float:
        """Day charge needs"""
        return self._schedule_info()["day"]

    def charge_total(self) -> float:
        """Total kWh required to charge"""
        return self._schedule_info()["total"]

    def min_soc(self) -> float:
        """Total kWh needed in the battery"""
        return self._schedule_info()["min_soc"]

    def clear_schedule(self, *args) -> None:
        """Clear schedule"""
        self._schedule.clear()
        self.refresh()

    def _schedule_info(self) -> float:
        """Schedule info"""
        return self._schedule.get(self._peak_utils.next_eco_start())

    def next_dawn_time(self) -> datetime:
        """Day charge needs"""
        return self._model.next_dawn_time()

    def todays_dawn_time_str(self) -> datetime:
        """Day charge needs"""
        return self._model.todays_dawn_time().isoformat()

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

    def set_boost(self, value: float) -> None:
        """Set boost on/off"""
        self._schedule.upsert(
            self._peak_utils.next_eco_start(), {"boost_status": value}
        )
        self.refresh()

    def get_boost(self) -> bool:
        """Boost status"""
        return self._get_boost(self._peak_utils.next_eco_start(), "boost_status")

    def set_full(self, status: bool) -> None:
        """Set full charge on/off"""
        value = self._capacity if status else 0
        self._schedule.upsert(self._peak_utils.next_eco_start(), {"full_status": value})
        self.refresh()

    def get_full(self) -> float:
        """Full status"""
        value = self._get_boost(self._peak_utils.next_eco_start(), "full_status")
        return False if value == 0 else True

    def _get_boost(self, index: datetime, charge_type: str) -> bool:
        """Retrieve schedule item"""
        schedule = self._schedule.get(index)
        if schedule is not None and charge_type in schedule:
            return schedule[charge_type]

        return 0

    def battery_depleted(self) -> datetime:
        """Time battery capacity is 0"""
        return self._model.battery_depleted_time()

    def peak_grid_import(self) -> float:
        """Grid import to next eco start"""
        return self._model.peak_grid_import()

    def peak_grid_export(self) -> float:
        """Grid export to next eco start"""
        return self._model.peak_grid_export()

    def empty(self) -> int:
        """Hack for hidden sensors"""
        return 0
