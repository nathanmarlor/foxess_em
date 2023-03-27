"""Home Assistant switch"""
import logging

from custom_components.foxess_em.common.number_desc import NumberDescription
from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_IDENTIFIERS
from homeassistant.const import ATTR_NAME
from homeassistant.helpers.device_registry import DeviceEntryType

from ..const import ATTR_ENTRY_TYPE
from ..const import DEFAULT_NAME
from ..const import DOMAIN
from ..const import NUMBER

_LOGGER = logging.getLogger(__name__)


class Number(NumberEntity):
    """Battery number class."""

    def __init__(
        self,
        controller,
        config_entry: ConfigEntry,
        number_desc: NumberDescription,
    ):
        self._controller = controller
        self._config_entry = config_entry
        self.number_desc = number_desc

        self._attr_device_info = {
            ATTR_IDENTIFIERS: {(DOMAIN, config_entry.entry_id)},
            ATTR_NAME: "FoxESS - Energy Management",
            ATTR_ENTRY_TYPE: DeviceEntryType.SERVICE,
        }

        self._unique_id = f"{DEFAULT_NAME}_{NUMBER}_{self.number_desc.name}"

    @property
    def name(self) -> str:
        """Return the name of the number."""
        return self.number_desc.name

    @property
    def native_value(self):
        """Return the state of the sensor."""
        number = getattr(self._controller, self.number_desc.get_method)
        return number()

    async def async_set_native_value(self, value: float) -> None:
        """Change the selected option."""
        number = getattr(self._controller, self.number_desc.set_method)
        number(value)

    @property
    def native_min_value(self):
        return self.number_desc.native_min_value

    @property
    def native_max_value(self):
        return self.number_desc.native_max_value

    @property
    def native_step(self):
        return self.number_desc.native_step

    @property
    def native_unit_of_measurement(self):
        return self.number_desc.native_unit_of_measurement

    @property
    def icon(self) -> str:
        """Return the icon of this number."""
        return self.number_desc.icon

    @property
    def unique_id(self) -> str:
        """Return the unique ID of the number"""
        return self._unique_id
