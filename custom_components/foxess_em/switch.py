"""Home Assistant switch"""
from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_IDENTIFIERS
from homeassistant.const import ATTR_NAME
from homeassistant.helpers.device_registry import DeviceEntryType

from .common.switch_desc import SwitchDescription
from .const import ATTR_ENTRY_TYPE
from .const import DEFAULT_NAME
from .const import DOMAIN
from .const import SWITCH

_SWITCHES: dict[str, SwitchDescription] = {
    "boost": SwitchDescription(
        key="boost",
        name="Boost Charge (+1kW)",
        icon="mdi:rocket",
        is_on="boost_status",
        switch="set_boost",
    ),
    "full": SwitchDescription(
        key="full",
        name="Full Charge",
        icon="mdi:rocket",
        is_on="full_status",
        switch="set_full",
    ),
    "disable": SwitchDescription(
        key="disable",
        name="Disable Auto Charge",
        icon="mdi:sync-off",
        is_on="disable_status",
        switch="set_disable",
    ),
}


async def async_setup_entry(hass, entry: ConfigEntry, async_add_devices):
    """Setup sensor platform."""
    controllers = hass.data[DOMAIN][entry.entry_id]["controllers"]

    entities = []

    for switch in _SWITCHES:
        sw = BatterySwitch(controllers["battery"], entry, _SWITCHES[switch])
        entities.append(sw)

    async_add_devices(entities)


class BatterySwitch(SwitchEntity):
    """Battery switch class."""

    def __init__(self, controller, config_entry, switch_desc):
        self._controller = controller
        self._config_entry = config_entry
        self._switch_desc = switch_desc

        self._attr_device_info = {
            ATTR_IDENTIFIERS: {(DOMAIN, config_entry.entry_id)},
            ATTR_NAME: "FoxESS - Energy Management",
            ATTR_ENTRY_TYPE: DeviceEntryType.SERVICE,
        }

        self._unique_id = f"{DEFAULT_NAME}_{SWITCH}_{self._switch_desc.name}"

    async def async_turn_on(self, **kwargs) -> None:  # pylint: disable=unused-argument
        """Turn on the switch."""
        switch = getattr(self._controller, self._switch_desc.switch)
        switch(True)

    async def async_turn_off(self, **kwargs) -> None:  # pylint: disable=unused-argument
        """Turn off the switch."""
        switch = getattr(self._controller, self._switch_desc.switch)
        switch(False)

    @property
    def name(self) -> str:
        """Return the name of the switch."""
        return self._switch_desc.name

    @property
    def icon(self) -> str:
        """Return the icon of this switch."""
        return self._switch_desc.icon

    @property
    def unique_id(self) -> str:
        """Return the unique ID of the binary sensor."""
        return self._unique_id

    @property
    def is_on(self) -> bool:
        """Return true if the switch is on."""
        is_on = getattr(self._controller, self._switch_desc.is_on)
        return is_on()
