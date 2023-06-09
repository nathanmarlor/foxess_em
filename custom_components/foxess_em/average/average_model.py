"""Average model"""
import logging
from datetime import datetime
from datetime import time

import pandas as pd
from dateutil import tz
from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder import history
from homeassistant.core import HomeAssistant

from ..util.exceptions import NoDataError
from .tracked_sensor import HistorySensor
from .tracked_sensor import TrackedSensor

_LOGGER = logging.getLogger(__name__)


class AverageModel:
    """Class to store history retrieval"""

    def __init__(
        self,
        hass: HomeAssistant,
        entities: dict[str, TrackedSensor],
        eco_start_time: time,
        eco_end_time: time,
    ) -> None:
        self._hass = hass
        self._tracked_sensors = entities
        self._resampled = {}
        self._ready = False
        self._eco_start_time = eco_start_time
        self._eco_end_time = eco_end_time

    def ready(self) -> bool:
        """Model status"""
        return self._ready

    async def refresh(self) -> None:
        """Refresh historical data"""
        # refresh all
        for sensor in self._tracked_sensors:
            await self._update_history(self._tracked_sensors[sensor])

        self._resampled = self._house_load_resample()
        self._ready = True

    async def _update_history(self, sensor: TrackedSensor) -> None:
        """Update history values"""

        await self._update_item(sensor.primary)

        for item in sensor.secondary:
            await self._update_item(item)

    async def _update_item(self, item: HistorySensor) -> None:
        """Retrieve values from HA"""
        recorder = get_instance(self._hass)

        to_date = datetime.now().astimezone()

        if item.whole_day:
            to_date = datetime.now().astimezone().replace(hour=0, minute=0, second=0, microsecond=0).astimezone(tz.UTC)

        from_date = to_date - item.period

        history_list = await recorder.async_add_executor_job(
            history.state_changes_during_period,
            self._hass,
            from_date,
            to_date,
            str(item.sensor_name),
        )

        values = history_list.get(item.sensor_name)

        values_dict = [
            {
                "datetime": value.last_changed.astimezone(tz.UTC),
                "value": float(value.state),
            }
            for value in values
            if value.state not in ("", "unknown", "unavailable")
        ]

        # Add start/final value to ensure even resampling later
        values_dict[0] = {
            "datetime": from_date.astimezone(tz.UTC),
            "value": 0,
        }

        values_dict.append(
            {
                "datetime": to_date.astimezone(tz.UTC),
                "value": values_dict[-1]["value"],
            }
        )

        item.values = values_dict

    def resample_data(self) -> pd.DataFrame:
        """Return resampled data"""
        if len(self._resampled) == 0:
            raise NoDataError("No house load data available")
        return self._resampled

    def _house_load_resample(self) -> pd.DataFrame:
        """Resample house load and deduct secondary sensors"""
        house_load_values = self._tracked_sensors["house_load_7d"].primary.values
        house_load_resample = self._resample_data(house_load_values)

        for aux in self._tracked_sensors["house_load_7d"].secondary:
            aux_load_resample = self._resample_data(aux.values)
            aux_load_resample["load"] = aux_load_resample["load"] / 1000
            house_load_resample["load"] -= aux_load_resample["load"]

        return house_load_resample

    def _resample_data(self, values) -> pd.DataFrame:
        """Resample values"""
        df = pd.DataFrame.from_dict(values)

        df = df.set_index("datetime").resample("1s").ffill().resample("1Min").mean()

        df = df.rename(columns={"value": "load"})
        df["load"] = df["load"] / 60

        df["datetime"] = pd.to_datetime(df.index.values, utc=True)
        df["time"] = df.datetime.dt.time

        return df

    def average_all_house_load(self) -> float:
        """House load today"""
        days = self._tracked_sensors["house_load_7d"].primary.period.days

        l_df = self._resampled

        return round(l_df.load.sum() / days, 2)

    def average_peak_house_load(self) -> float:
        """House load peak"""
        days = self._tracked_sensors["house_load_7d"].primary.period.days

        eco_start = (
            datetime.now()
            .astimezone()
            .replace(
                hour=self._eco_start_time.hour,
                minute=self._eco_start_time.minute,
                second=0,
                microsecond=0,
            )
        )
        eco_start = eco_start.astimezone(tz.UTC).time()
        eco_end = (
            datetime.now()
            .astimezone()
            .replace(
                hour=self._eco_end_time.hour,
                minute=self._eco_end_time.minute,
                second=0,
                microsecond=0,
            )
        )
        eco_end = eco_end.astimezone(tz.UTC).time()

        l_df = self._resampled
        filtered = l_df.between_time(eco_end, eco_start)

        return round(filtered.load.sum() / days, 2)
