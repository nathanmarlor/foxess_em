"""Solcast sensor"""

import logging

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import UnitOfEnergy

from ..common.sensor import Sensor
from ..common.sensor_desc import SensorDescription

_LOGGER: logging.Logger = logging.getLogger(__package__)

SENSORS: dict[str, SensorDescription] = {
    "total_kwh_forecast_today": SensorDescription(
        key="total_kwh_forecast_today",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        name="Forecast: Today",
        icon="mdi:solar-power",
    ),
    "total_kwh_forecast_tomorrow": SensorDescription(
        key="total_kwh_forecast_tomorrow",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        name="Forecast: Tomorrow",
        icon="mdi:solar-power",
    ),
    "total_kwh_forecast_today_remaining": SensorDescription(
        key="total_kwh_forecast_today_remaining",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        name="Forecast: Today Remaining",
        icon="mdi:solar-power",
        should_poll=True,
    ),
    "api_count": SensorDescription(
        key="api_count",
        device_class=None,
        name="Forecast: API Count",
        icon="mdi:counter",
    ),
    "forecast": SensorDescription(
        key="empty",
        name="FoxESS EM: Forecast",
        icon="mdi:calendar",
        should_poll=False,
        visible=False,
        state_attributes={"forecast": "raw_data", "last_update": "last_update"},
        store_attributes=True,
    ),
}


def sensors(controllers, entry) -> list:
    """Setup sensor platform."""
    entities = []

    for sensor in SENSORS:
        sen = Sensor(controllers["forecast"], SENSORS[sensor], entry)
        entities.append(sen)

    return entities
