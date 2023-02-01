"""Home Assistant switch"""
import logging

from homeassistant.components.sensor import RestoreEntity
from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_IDENTIFIERS
from homeassistant.const import ATTR_NAME
from homeassistant.helpers.device_registry import DeviceEntryType

from ..common.switch_desc import SwitchDescription
from ..const import ATTR_ENTRY_TYPE
from ..const import DEFAULT_NAME
from ..const import DOMAIN
from ..const import SWITCH

_LOGGER = logging.getLogger(__name__)


class Switch(SwitchEntity, RestoreEntity):
    """Battery switch class."""

    def __init__(
        self, controller, config_entry: ConfigEntry, switch_desc: SwitchDescription
    ):
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

    async def async_added_to_hass(self) -> None:
        """Add update callback after being added to hass."""
        await super().async_added_to_hass()
        state = await self.async_get_last_state()
        if state and self._switch_desc.store_state:
            if state.state:
                await self.async_turn_on()
            else:
                await self.async_turn_off()
