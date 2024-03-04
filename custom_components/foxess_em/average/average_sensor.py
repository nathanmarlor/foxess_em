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
}


def sensors(controllers, entry) -> list:
    """Setup sensor platform."""
    entities = []

    for sensor in SENSORS:
        sen = Sensor(controllers["average"], SENSORS[sensor], entry)
        entities.append(sen)

    return entities
