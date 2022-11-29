"""Calendar entries"""
import logging
from datetime import datetime

from custom_components.foxess_em.const import DOMAIN
from homeassistant.components.calendar import CalendarEntity
from homeassistant.components.calendar import CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

_LOGGER: logging.Logger = logging.getLogger(__package__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
):
    """Setup calendar entry"""
    controllers = hass.data[DOMAIN][entry.entry_id]["controllers"]
    calendar = FoxESSCalendar(controllers["battery"])
    async_add_entities([calendar], update_before_add=True)


class FoxESSCalendar(CalendarEntity):
    """FoxESS Calendar"""

    def __init__(self, controller):
        self._controller = controller
        self._event: CalendarEvent | None = None
        self._name = "FoxESS Energy Management"

    @property
    def event(self) -> CalendarEvent | None:
        return self._event

    @property
    def name(self):
        """Return the name of the entity."""
        return self._name

    async def async_get_events(
        self,
        hass: HomeAssistant,
        start_date: datetime,
        end_date: datetime,
    ) -> list[CalendarEvent]:
        """Return all events within a time window"""

        events = self._controller.get_schedule()

        calendar_events = []
        for key in events:
            values = events[key]
            summary = "Charge: " + str(round(values["total"], 2))
            summary += " Start Capacity: " + str(round(values["battery"], 2))
            summary += " Forecast: " + str(round(values["forecast"], 2))
            summary += " Load: " + str(round(values["load"], 2))
            summary += " Min SoC: " + str(round(values["min_soc"], 2))
            calendar_events.append(CalendarEvent(key, values["eco_end"], summary))

        return calendar_events
