"""Charge service"""
import logging
from datetime import time

from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_point_in_time
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
    ) -> None:
        """Init charge service"""
        UnloadController.__init__(self)
        self._hass = hass
        self._battery_controller = battery_controller
        self._forecast_controller = forecast_controller
        self._fox = fox
        self._eco_start_time = eco_start_time
        self._eco_end_time = eco_end_time
        self._cancel_charge_listener = None
        self._charge_active = False
        self._perc_target = 0

        # Setup trigger to start when eco period starts
        eco_start = async_track_utc_time_change(
            self._hass,
            self._set_schedule,
            hour=eco_start_time.hour,
            minute=eco_start_time.minute,
            second=0,
            local=True,
        )
        self._unload_listeners.append(eco_start)

        # Setup trigger to stop when eco period ends - in case charging overruns
        eco_end = async_track_utc_time_change(
            self._hass,
            self._stop_force_charge,
            hour=eco_end_time.hour,
            minute=eco_end_time.minute,
            second=0,
            local=True,
        )
        self._unload_listeners.append(eco_end)

    async def _set_schedule(self, *args) -> None:  # pylint: disable=unused-argument
        """Configure battery needs"""
        _LOGGER.debug("Configuring battery schedule")

        await self._forecast_controller.async_refresh()

        charge_total = self._battery_controller.charge_total()

        if charge_total > 0:
            self._perc_target = self._battery_controller.charge_to_perc()
            start_time = self._battery_controller.charge_start_time()

            _LOGGER.debug(
                f"Setting schedule at {start_time} to charge to {self._perc_target}"
            )

            async_track_point_in_time(
                self._hass, self._start_force_charge, point_in_time=start_time
            )

        else:
            _LOGGER.debug("No charge required")

    async def _start_force_charge(
        self, *args
    ) -> None:  # pylint: disable=unused-argument
        """Initiate force charging"""
        _LOGGER.debug(f"Starting force charge to {self._perc_target}")

        self._charge_active = True

        # Setup trigger to stop charge when target percentage is met
        start_charge = async_track_state_change(
            self._hass,
            "sensor.battery_soc",
            self._stop_force_charge,
            str(int(self._perc_target) - 1),
            str(int(self._perc_target)),
        )

        self._cancel_charge_listener = start_charge
        self._unload_listeners.append(start_charge)

        await self._fox.start_force_charge()

    async def _stop_force_charge(
        self, *args
    ) -> None:  # pylint: disable=unused-argument
        """Stop force charging"""

        if self._charge_active:
            _LOGGER.debug("Stopping force charge")

            self._charge_active = False

            # Reset boost/full status for the next day
            self._battery_controller.set_boost(False)
            self._battery_controller.set_full(False)

            await self._fox.stop_force_charge()

            self._cancel_charge_listener()
