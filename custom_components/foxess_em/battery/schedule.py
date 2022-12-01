"""Battery controller"""
import logging
from datetime import datetime
from typing import Any

from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)
_SCHEDULE = "sensor.foxess_em_schedule"


class Schedule:
    """Schedule"""

    def __init__(self, hass: HomeAssistant) -> None:
        """Get persisted schedule from states"""
        self._hass = hass
        self._schedule = {}

    def load(self) -> None:
        """Load schedule from state"""
        schedule = self._hass.states.get(_SCHEDULE)

        if schedule is not None and "schedule" in schedule.attributes:
            self._schedule = schedule.attributes["schedule"]
        else:
            self._schedule = {}

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
