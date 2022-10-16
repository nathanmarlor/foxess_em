"""Sensor platform for foxess_em."""
import logging

from homeassistant.config_entries import ConfigEntry

from .average import average_sensor
from .battery import battery_sensor
from .const import DOMAIN
from .forecast import forecast_sensor

_LOGGER: logging.Logger = logging.getLogger(__package__)


async def async_setup_entry(hass, entry: ConfigEntry, async_add_devices) -> None:
    """Setup sensor platform."""

    controllers = hass.data[DOMAIN][entry.entry_id]["controllers"]

    # Prime history for sensor creation
    await controllers["forecast"].async_refresh()
    await controllers["average"].async_refresh()
    await controllers["battery"].async_refresh()

    # Add callbacks into battery controller for updates
    controllers["forecast"].add_update_listener(controllers["battery"])
    controllers["average"].add_update_listener(controllers["battery"])

    history_sensors = average_sensor.sensors(controllers, entry)
    solcast_sensors = forecast_sensor.sensors(controllers, entry)
    battery_sensors = battery_sensor.sensors(controllers, entry)

    entities = solcast_sensors + history_sensors + battery_sensors

    async_add_devices(entities)
