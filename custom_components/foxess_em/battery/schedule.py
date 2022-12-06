"""Battery controller"""
import logging
from datetime import datetime
from datetime import timedelta
from typing import Any

from custom_components.foxess_em.common.hass_load_controller import HassLoadController
from custom_components.foxess_em.common.unload_controller import UnloadController
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_utc_time_change

_LOGGER = logging.getLogger(__name__)
_SCHEDULE = "sensor.foxess_em_schedule"


class Schedule(HassLoadController, UnloadController):
    """Schedule"""

    def __init__(self, hass: HomeAssistant) -> None:
        """Get persisted schedule from states"""
        UnloadController.__init__(self)
        HassLoadController.__init__(self, hass, self.load)
        self._hass = hass
        self._schedule = {}

        # Housekeeping on schedule
        housekeeping = async_track_utc_time_change(
            self._hass,
            self._housekeeping,
            hour=0,
            minute=0,
            second=10,
            local=False,
        )
        self._unload_listeners.append(housekeeping)

    def load(self, *args) -> None:
        """Load schedule from state"""
        schedule = self._hass.states.get(_SCHEDULE)

        if schedule is not None and "schedule" in schedule.attributes:
            self._schedule = schedule.attributes["schedule"]
        else:
            self._schedule = {}

        self._housekeeping()

    def upsert(self, index: datetime, params: dict) -> None:
        """Update or insert new item"""
        _LOGGER.debug(f"Updating schedule {index}: {params}")

        index = index.isoformat()
        if index in self._schedule:
            self._schedule[index].update(params)
        else:
            self._schedule[index] = params

    def get_all(self) -> dict[str, dict[str, Any]] | None:
        """Retrieve schedule item"""
        return self._schedule

    def get(self, index: datetime) -> dict[str, Any] | None:
        """Retrieve schedule item"""
        index = index.isoformat()

        if index in self._schedule:
            return self._schedule[index]
        else:
            return None

    def _housekeeping(self, *args) -> None:
        """Clean up schedule"""
        two_weeks_ago = datetime.now().astimezone() - timedelta(days=14)

        for schedule in list(self._schedule.keys()):
            if datetime.fromisoformat(schedule) < two_weeks_ago:
                _LOGGER.debug(f"Schedule housekeeping, removing data for {schedule}")
                self._schedule.pop(schedule)
