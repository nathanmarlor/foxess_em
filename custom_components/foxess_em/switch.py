"""Home Assistant switch"""
from homeassistant.config_entries import ConfigEntry

from .battery import battery_switch
from .charge import charge_switch
from .const import Connection
from .const import DOMAIN


async def async_setup_entry(hass, entry: ConfigEntry, async_add_devices):
    """Setup sensor platform."""
    controllers = hass.data[DOMAIN][entry.entry_id]["controllers"]
    config = hass.data[DOMAIN][entry.entry_id]["config"]

    charge_switches = charge_switch.switches(controllers, entry)
    battery_switches = battery_switch.switches(controllers, entry)

    entities = charge_switches + battery_switches

    entities = [
        entity
        for entity in entities
        if (entity.switch_desc.connection == Connection.BOTH) or (entity.switch_desc.connection == config["connection"])
    ]

    async_add_devices(entities)
