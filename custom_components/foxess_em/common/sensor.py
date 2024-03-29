"""Sensor"""

import logging
from typing import Any

from attr import dataclass
from homeassistant.components.sensor import (
    ExtraStoredData,
    RestoreEntity,
    SensorDeviceClass,
    SensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_IDENTIFIERS, ATTR_NAME
from homeassistant.helpers.device_registry import DeviceEntryType

from custom_components.foxess_em.common.callback_controller import CallbackController

from ..const import ATTR_ENTRY_TYPE, DOMAIN
from .sensor_desc import SensorDescription

_LOGGER = logging.getLogger(__name__)


class Sensor(SensorEntity, RestoreEntity):
    """Sensor class."""

    def __init__(
        self,
        controller: CallbackController,
        entity_description: SensorDescription,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""

        self._controller = controller
        self._entity_description = entity_description

        self._attributes = {}
        self._attr_extra_state_attributes = {}
        self._attr_entity_registry_visible_default = entity_description.visible
        self._attr_entity_registry_enabled_default = entity_description.enabled

        self._attr_device_info = {
            ATTR_IDENTIFIERS: {(DOMAIN, entry.entry_id)},
            ATTR_NAME: "FoxESS - Energy Management",
            ATTR_ENTRY_TYPE: DeviceEntryType.SERVICE,
        }

        self._unique_id = f"foxess_em_{entity_description.name}"

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self._entity_description.name

    @property
    def native_value(self):
        """Return the value reported by the sensor."""
        if self._controller.ready():
            for value in self._entity_description.state_attributes:
                extra_method = getattr(
                    self._controller, self._entity_description.state_attributes[value]
                )
                self._attr_extra_state_attributes[value] = extra_method()

            method = getattr(self._controller, self._entity_description.key)
            return method()

    @property
    def native_unit_of_measurement(self) -> str:
        """Return native unit of measurement"""
        return self._entity_description.native_unit_of_measurement

    @property
    def icon(self) -> str:
        """Return the icon of the sensor."""
        return self._entity_description.icon

    @property
    def device_class(self) -> SensorDeviceClass:
        """Return the device class of the sensor."""
        return self._entity_description.device_class

    @property
    def unique_id(self) -> str:
        """Return the unique ID of the binary sensor."""
        return self._unique_id

    @property
    def should_poll(self) -> bool:
        """Return True if entity has to be polled for state.
        False if entity pushes its state to HA.
        """
        return self._entity_description.should_poll

    @property
    def extra_restore_state_data(self) -> ExtraStoredData:
        """Return specific state data to be restored."""
        if self._entity_description.store_attributes:
            return SensorExtraData(self._attr_extra_state_attributes)

    def update_callback(self) -> None:
        """Schedule a state update."""
        self.schedule_update_ha_state(True)

    async def async_added_to_hass(self) -> None:
        """Add update callback after being added to hass."""
        await super().async_added_to_hass()
        self._controller.add_update_listener(self)
        state = await self.async_get_last_state()
        if state:
            if self._entity_description.store_attributes and state.attributes:
                self._attr_extra_state_attributes = dict(state.attributes)
            if self._entity_description.store_state:
                self._attr_state = state.state


@dataclass
class SensorExtraData(ExtraStoredData):
    """Object to hold extra stored data."""

    attributes: dict[str, Any] | None

    def as_dict(self) -> dict[str, Any]:
        """Return a dict representation of additional data."""
        return self.attributes

    @classmethod
    def from_dict(cls, restored: dict[str, Any]):
        """Save a dict representation of additional data"""
        return cls(restored)
