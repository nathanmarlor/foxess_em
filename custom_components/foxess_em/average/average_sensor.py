"""Average sensor"""
import logging

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import ENERGY_KILO_WATT_HOUR

from ..common.sensor import Sensor
from ..common.sensor_desc import SensorDescription

_LOGGER = logging.getLogger(__name__)

SENSORS: dict[str, SensorDescription] = {
    "average_all_house_load": SensorDescription(
        key="average_all_house_load",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        name="Load: Daily",
        icon="mdi:battery",
        should_poll=False,
    ),
    "average_peak_house_load": SensorDescription(
        key="average_peak_house_load",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        name="Load: Peak",
        icon="mdi:battery",
        should_poll=False,
    ),
    "average_house_load_15m": SensorDescription(
        key="house_load_15m",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        name="Load: Last 15m",
        icon="mdi:battery",
        should_poll=True,
    ),
}


def sensors(controllers, entry) -> list:
    """Setup sensor platform."""
    entities = []

    for sensor in SENSORS:
        sen = TimeSeriesAverageSensor(controllers["average"], SENSORS[sensor], entry)
        entities.append(sen)

    return entities


class TimeSeriesAverageSensor(Sensor):
    """Time series overload"""

    async def async_update(self) -> None:
        """Retrieve latest state."""
        if self._entity_description.should_poll:
            await self._controller.async_refresh(sensor_id=self._entity_description.key)
