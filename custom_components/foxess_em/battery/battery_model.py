"""Battery model"""
import logging
from datetime import datetime
from datetime import time
from datetime import timedelta

import pandas as pd
from homeassistant.core import HomeAssistant

from ..util.exceptions import NoDataError

_LOGGER = logging.getLogger(__name__)


class BatteryModel:
    """Class to manage battery values"""

    def __init__(
        self,
        hass: HomeAssistant,
        min_soc: float,
        capacity: float,
        dawn_buffer: float,
        day_buffer: float,
        charge_rate: float,
        eco_start_time: time,
        eco_end_time: time,
        battery_soc: str,
    ) -> None:
        self._hass = hass
        self._model = None
        self._ready = False
        self._min_soc = min_soc
        self._capacity = capacity
        self._dawn_buffer = dawn_buffer
        self._day_buffer = day_buffer
        self._charge_rate = charge_rate
        self._eco_start_time = eco_start_time
        self._eco_end_time = eco_end_time
        self._battery_soc = battery_soc

    def ready(self) -> bool:
        """Model status"""
        return self._ready

    def battery_capacity_remaining(self) -> float:
        """Usable capacity remaining"""
        battery_state = self._hass.states.get(self._battery_soc)
        if battery_state is None:
            raise NoDataError("Battery state is invalid")
        if battery_state.state in ["unknown", "unavailable"]:
            raise NoDataError("Battery state is unknown")

        battery_soc = int(battery_state.state)
        battery_capacity = (battery_soc / 100) * self._capacity

        return battery_capacity - (self._min_soc * self._capacity)

    def charge_to_perc(self, charge: float) -> float:
        """Convert kWh to percentage of charge"""
        perc = ((charge / self._capacity) + self._min_soc) * 100

        return min(99, round(perc, 0))

    def charge_start_time(self, charge: float) -> datetime:
        """Convert kWh to time to charge"""
        minutes = (charge / self._charge_rate) * 60
        delta = timedelta(minutes=minutes)

        start_time = self._next_eco_end_time() - delta

        return start_time

    def refresh_battery_model(self, forecast: pd.DataFrame, load: pd.DataFrame) -> None:
        """Calculate battery model"""

        load = load.groupby(load["time"]).mean()
        load["time"] = load.index.values

        now = datetime.utcnow()

        forecast = forecast[
            (forecast["date"] >= now.date())
            & (forecast["date"] <= (now + timedelta(days=1)).date())
        ]

        load.reset_index(drop=True, inplace=True)
        forecast.reset_index(drop=True, inplace=True)

        merged = pd.merge(load, forecast, how="right", on=["time"])
        merged["delta"] = merged["pv_estimate"] - merged["load"]

        merged = merged.reset_index(drop=True)

        merged = merged.sort_values(by="period_start")

        battery = self.battery_capacity_remaining()
        battery_states = []
        available_capacity = self._capacity - (self._min_soc * self._capacity)
        for index, _ in merged.iterrows():
            if merged.iloc[index]["period_start"] >= datetime.now().astimezone():
                delta = merged.iloc[index]["delta"]
                battery = max([0, min([available_capacity, battery + delta])])
                battery_states.append(battery)
            else:
                battery_states.append(0)

        merged["battery"] = battery_states

        self._model = merged
        self._ready = True

    def state_at_eco_start(self) -> float:
        """State at eco end"""
        return self._state_at_datetime(self._next_eco_start_time())

    def state_at_eco_end(self) -> float:
        """State at eco end"""
        return self._state_at_datetime(self._next_eco_end_time())

    def state_at_dawn(self) -> float:
        """State at eco end"""
        return self._state_at_datetime(self.next_dawn_time())

    def dawn_load(self) -> float:
        """Dawn load"""
        dawn_time = self.next_dawn_time()
        eco_time = self._next_eco_end_time()

        dawn_load = self._model[
            (
                (self._model["period_start"] > eco_time)
                & (self._model["period_start"] < dawn_time)
            )
        ]

        load_sum = abs(dawn_load.delta.sum())

        return round(load_sum, 2)

    def dawn_charge_needs(self) -> float:
        """Dawn charge needs"""
        if self._is_after_todays_eco_end() and self._is_before_todays_dawn():
            return 0

        eco_start = self.state_at_eco_start()
        dawn_load = self.dawn_load()

        dawn_charge_needs = eco_start - dawn_load

        dawn_buffer_top_up = self._dawn_buffer - dawn_charge_needs

        ceiling = self.ceiling_charge_total(dawn_buffer_top_up)

        return round(ceiling, 2)

    def next_dawn_time(self) -> datetime:
        """Calculate dawn time"""
        now = datetime.now().astimezone()

        dawn_today = self._dawn_time(now)
        dawn_tomorrow = self._dawn_time(now + timedelta(days=1))

        if now > dawn_today:
            return dawn_tomorrow
        else:
            return dawn_today

    def todays_dawn_time(self) -> datetime:
        """Calculate dawn time"""
        now = datetime.now().astimezone()
        return self._dawn_time(now)

    def _dawn_time(self, date: datetime) -> datetime:
        """Calculate dawn time"""
        filtered = self._model[self._model["date"] == date.date()]
        dawn = filtered[filtered["delta"] > 0]

        if len(dawn) == 0:
            # Solar never reaches house load... return mid-day
            return date.replace(hour=12, minute=0, second=0, microsecond=0)
        else:
            return self._model.iloc[dawn["period_start"].idxmin()].period_start

    def day_charge_needs(
        self,
        forecast_today: float,
        forecast_tomorrow: float,
        state_at_eco_start: float,
        house_load: float,
    ) -> float:
        """Day charge needs"""
        if self._is_after_todays_eco_end():
            forecast = forecast_tomorrow
        else:
            forecast = forecast_today

        day_charge_needs = (state_at_eco_start - house_load) + forecast

        day_buffer_top_up = self._day_buffer - day_charge_needs

        ceiling = self.ceiling_charge_total(day_buffer_top_up)

        return round(ceiling, 2)

    def ceiling_charge_total(self, charge_total: float) -> float:
        """Ceiling total charge"""
        available_capacity = round(
            self._capacity
            - (self._min_soc * self._capacity)
            - self.state_at_eco_start(),
            2,
        )

        return min(available_capacity, charge_total)

    def _state_at_datetime(self, time: datetime) -> float:
        """Battery and forecast remaining meets load until dawn"""
        time = time.replace(second=0, microsecond=0)
        return self._model[self._model["period_start"] == time].battery.iloc[0]

    def _next_eco_end_time(self) -> datetime:
        """Next eco end time"""
        now = datetime.now().astimezone()
        eco_end = now.replace(
            hour=self._eco_end_time.hour,
            minute=self._eco_end_time.minute,
            second=0,
            microsecond=0,
        )
        if now > eco_end:
            eco_end += timedelta(days=1)

        return eco_end

    def _next_eco_start_time(self) -> datetime:
        """Next eco start time"""
        now = datetime.now().astimezone()
        eco_start = now.replace(
            hour=self._eco_start_time.hour,
            minute=self._eco_start_time.minute,
            second=0,
            microsecond=0,
        )
        if now > eco_start:
            eco_start += timedelta(days=1)

        return eco_start

    def _is_after_todays_eco_end(self) -> bool:
        """Is current time after eco period end"""
        now = datetime.now().astimezone()
        eco_end = now.replace(
            hour=self._eco_end_time.hour,
            minute=self._eco_end_time.minute,
            second=0,
            microsecond=0,
        )
        return now > eco_end

    def _is_before_todays_dawn(self) -> bool:
        """Is current time after eco period end"""
        now = datetime.now().astimezone()
        dawn_time = self.todays_dawn_time()
        return now < dawn_time
