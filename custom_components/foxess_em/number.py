"""Home Assistant switch"""
from homeassistant.config_entries import ConfigEntry

from .battery import battery_number
from .const import DOMAIN


async def async_setup_entry(hass, entry: ConfigEntry, async_add_devices):
    """Setup sensor platform."""
    controllers = hass.data[DOMAIN][entry.entry_id]["controllers"]

    entities = battery_number.numbers(controllers, entry)

    async_add_devices(entities)
