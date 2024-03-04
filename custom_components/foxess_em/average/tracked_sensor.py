"""Tracked sensor data model"""

from dataclasses import dataclass
from datetime import timedelta


@dataclass
class HistorySensor:
    """ "History sensor model"""

    sensor_name: str
    period: timedelta
    whole_day: bool | None = False
    values: list[dict] | None = None


@dataclass
class TrackedSensor:
    """ "Tracked sensor model"""

    primary: HistorySensor
    secondary: list[HistorySensor]
