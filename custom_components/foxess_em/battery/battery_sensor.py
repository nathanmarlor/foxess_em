"""Battery sensor"""
import logging

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import ENERGY_KILO_WATT_HOUR

from ..common.sensor import Sensor
from ..common.sensor_desc import SensorDescription

_LOGGER = logging.getLogger(__name__)

SENSORS: dict[str, SensorDescription] = {
    "charge_total": SensorDescription(
        key="charge_total",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        name="Capacity: Charge Needed",
        icon="mdi:flash",
        should_poll=False,
        state_attributes={
            "Dawn Charge Needed:": "dawn_charge_needs",
            "Day Charge Needed:": "day_charge_needs",
            "Target %:": "charge_to_perc",
        },
    ),
    "state_at_eco_start": SensorDescription(
        key="state_at_eco_start",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        name="Capacity: Eco Start",
        icon="mdi:meter-electric",
        should_poll=False,
        state_attributes={},
    ),
    "state_at_eco_end": SensorDescription(
        key="state_at_eco_end",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        name="Capacity: Eco End",
        icon="mdi:meter-electric",
        should_poll=False,
        state_attributes={},
    ),
    "state_at_dawn": SensorDescription(
        key="state_at_dawn",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        name="Capacity: Dawn",
        icon="mdi:sun-clock",
        should_poll=False,
        state_attributes={},
    ),
    "next_dawn_time": SensorDescription(
        key="next_dawn_time",
        device_class=SensorDeviceClass.TIMESTAMP,
        native_unit_of_measurement=None,
        name="Capacity: Next Dawn Time",
        icon="mdi:sun-clock",
        should_poll=False,
        state_attributes={"Todays Dawn:": "todays_dawn_time_str"},
    ),
    "last_update": SensorDescription(
        key="battery_last_update",
        device_class=SensorDeviceClass.TIMESTAMP,
        name="Last Update",
        icon="mdi:clock",
        should_poll=False,
        state_attributes={
            "Battery:": "battery_last_update_str",
            "Forecast:": "forecast_last_update_str",
            "Average:": "average_last_update_str",
        },
    ),
}


def sensors(controllers, entry) -> list:
    """Setup sensor platform."""
    entities = []

    for sensor in SENSORS:
        sen = Sensor(controllers["battery"], SENSORS[sensor], entry)
        entities.append(sen)

    return entities
