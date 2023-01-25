"""Charge service"""
import logging
from datetime import date
from datetime import datetime
from datetime import time
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_state_change
from homeassistant.helpers.event import async_track_utc_time_change

from ..battery.battery_controller import BatteryController
from ..common.unload_controller import UnloadController
from ..forecast.forecast_controller import ForecastController
from ..fox.fox_cloud_service import FoxCloudService

_LOGGER = logging.getLogger(__name__)


class ChargeService(UnloadController):
    """Charge service"""

    def __init__(
        self,
        hass: HomeAssistant,
        battery_controller: BatteryController,
        forecast_controller: ForecastController,
        fox: FoxCloudService,
        eco_start_time: time,
        eco_end_time: time,
        battery_soc: str,
        original_soc: int,
    ) -> None:
        """Init charge service"""
        UnloadController.__init__(self)
        self._hass = hass
        self._battery_controller = battery_controller
        self._forecast_controller = forecast_controller
        self._fox = fox
        self._eco_start_time = eco_start_time
        self._eco_end_time = eco_end_time
        self._battery_soc = battery_soc
        self._original_soc = original_soc
        self._cancel_listeners = []
        self._charge_active = False
        self._perc_target = 0
        self._charge_required = 0
        self._disable = False

        self._add_listeners()

    def _add_listeners(self) -> None:

        # Setup trigger to start just before eco period starts
        eco_start_setup_time = (
            datetime.combine(date.today(), self._eco_start_time) - timedelta(minutes=5)
        ).time()
        eco_start_setup = async_track_utc_time_change(
            self._hass,
            self._eco_start_setup,
            hour=eco_start_setup_time.hour,
            minute=eco_start_setup_time.minute,
            second=0,
            local=True,
        )
        self._unload_listeners.append(eco_start_setup)

        # Setup trigger to start when eco period starts
        eco_start = async_track_utc_time_change(
            self._hass,
            self._eco_start,
            hour=self._eco_start_time.hour,
            minute=self._eco_start_time.minute,
            second=0,
            local=True,
        )
        self._unload_listeners.append(eco_start)

        # Setup trigger to stop when eco period ends
        eco_end = async_track_utc_time_change(
            self._hass,
            self._eco_end,
            hour=self._eco_end_time.hour,
            minute=self._eco_end_time.minute,
            second=0,
            local=True,
        )
        self._unload_listeners.append(eco_end)

    async def _eco_start_setup(self, *args) -> None:  # pylint: disable=unused-argument
        """Set target SoC"""

        _LOGGER.debug("Calculating optimal battery SoC")
        await self._forecast_controller.async_refresh()
        self._charge_required = self._battery_controller.charge_total()
        self._perc_target = self._battery_controller.charge_to_perc()

        _LOGGER.debug("Resetting any existing Fox Cloud force charge/min SoC settings")
        await self._start_force_charge()
        await self._fox.set_min_soc(self._original_soc * 100)

    async def _eco_start(self, *args) -> None:  # pylint: disable=unused-argument
        """Eco start"""

        _LOGGER.debug(f"Setting min SoC to {self._perc_target}%")
        await self._fox.set_min_soc(self._perc_target)

        self._start_listening()

        if self._charge_required <= 0:
            _LOGGER.debug(
                f"Allowing battery to continue discharge until {self._perc_target}"
            )
            await self._stop_force_charge()

        _LOGGER.debug("Resetting switches")
        self._battery_controller.set_boost(False)
        self._battery_controller.set_full(False)

    async def _start_force_charge(
        self, *args
    ) -> None:  # pylint: disable=unused-argument
        """Set Fox force charge settings to True"""
        self._charge_active = True
        await self._fox.start_force_charge_off_peak()

    async def _stop_force_charge(
        self, *args
    ) -> None:  # pylint: disable=unused-argument
        """Set Fox force charge settings to False"""
        self._charge_active = False
        await self._fox.stop_force_charge()

    async def _eco_end(self, *args) -> None:  # pylint: disable=unused-argument
        """Stop holding SoC"""

        self._stop_listening()

        # Reset Fox force charge to enabled
        await self._start_force_charge()

        _LOGGER.debug("Releasing SoC hold")
        await self._fox.set_min_soc(self._original_soc * 100)

    async def _battery_soc_change(
        self, entity, old_state, new_state
    ):  # pylint: disable=unused-argument
        new_state = float(new_state.state)

        if (new_state >= self._perc_target) and self._charge_active:
            await self._stop_force_charge()
        elif new_state < self._perc_target and not self._charge_active:
            await self._start_force_charge()

    def _start_listening(self):
        # Setup trigger to stop charge when target percentage is met
        track_charge = async_track_state_change(
            self._hass,
            self._battery_soc,
            self._battery_soc_change,
        )
        self._cancel_listeners.append(track_charge)
        self._unload_listeners.append(track_charge)

    def _stop_listening(self):
        # Stop listening for updates
        for listener in self._cancel_listeners:
            listener()
            # Remove any dangling references in unload listeners
            if listener in self._unload_listeners:
                self._unload_listeners.remove(listener)
        self._cancel_listeners.clear()

    def set_disable(self, status: bool) -> None:
        """Set disable on/off"""
        self._disable = status

        if status:
            self.unload()
        else:
            self._add_listeners()

    def disable_status(self) -> bool:
        """Disable status"""
        return self._disable
