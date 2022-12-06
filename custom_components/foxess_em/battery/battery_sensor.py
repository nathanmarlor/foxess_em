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
            "Dawn Min SoC:": "dawn_charge_needs",
            "Day Min SoC:": "day_charge_needs",
            "Min SoC %:": "charge_to_perc",
        },
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
    "state_at_eco_start": SensorDescription(
        key="state_at_eco_start",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        name="Capacity: Eco Start",
        icon="mdi:meter-electric",
        should_poll=False,
        state_attributes={},
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
    "peak_grid_import": SensorDescription(
        key="peak_grid_import",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        name="Capacity: Peak Grid Import",
        icon="mdi:credit-card-clock-outline",
        should_poll=False,
        state_attributes={},
    ),
    "peak_grid_export": SensorDescription(
        key="peak_grid_export",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        name="Capacity: Peak Grid Export",
        icon="mdi:credit-card-clock-outline",
        should_poll=False,
        state_attributes={},
    ),
    "battery_depleted": SensorDescription(
        key="battery_depleted",
        device_class=SensorDeviceClass.TIMESTAMP,
        native_unit_of_measurement=None,
        name="Capacity: Battery Empty Time",
        icon="mdi:battery-outline",
        should_poll=False,
        state_attributes={},
    ),
    "raw_data": SensorDescription(
        key="empty",
        name="FoxESS EM: Raw Data",
        icon="mdi:flash",
        should_poll=False,
        visible=False,
        state_attributes={
            "raw_data": "raw_data",
        },
        enabled=False,
    ),
    "schedule": SensorDescription(
        key="empty",
        name="FoxESS EM: Schedule",
        icon="mdi:calendar",
        should_poll=False,
        visible=False,
        state_attributes={
            "schedule": "get_schedule",
        },
        store_attributes=True,
    ),
}


def sensors(controllers, entry) -> list:
    """Setup sensor platform."""
    entities = []

    for sensor in SENSORS:
        sen = Sensor(controllers["battery"], SENSORS[sensor], entry)
        entities.append(sen)

    return entities
