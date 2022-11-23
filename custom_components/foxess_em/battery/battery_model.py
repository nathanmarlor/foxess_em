"""Battery model"""
import json
import logging
from datetime import datetime
from datetime import time
from datetime import timedelta

import pandas as pd
from homeassistant.core import HomeAssistant

from ..util.exceptions import NoDataError

_LOGGER = logging.getLogger(__name__)
_MAX_PERC = 100


class BatteryModel:
    """Class to manage battery values"""

    def __init__(
        self,
        hass: HomeAssistant,
        min_soc: float,
        capacity: float,
        dawn_buffer: float,
        day_buffer: float,
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

        return min(_MAX_PERC, round(perc, 0))

    def raw_data(self):
        """Return raw data in dictionary form"""
        now = datetime.now().astimezone()

        filtered = self._model[
            ["period_start", "pv_estimate", "load", "battery", "grid"]
        ]

        filtered = filtered.set_index("period_start").resample("5Min").mean()
        filtered["period_start"] = pd.to_datetime(filtered.index.values, utc=True)

        hist = filtered[filtered["period_start"] <= now]
        future = filtered[filtered["period_start"] > now]

        raw_data = {
            "history": json.loads(hist.to_json(orient="records")),
            "forecast": json.loads(future.to_json(orient="records")),
        }

        return json.dumps(raw_data)

    def refresh_battery_model(self, forecast: pd.DataFrame, load: pd.DataFrame) -> None:
        """Calculate battery model"""
        now = datetime.now().astimezone()

        load_forecast = self._merge_dataframes(load, forecast)

        # first refresh
        if self._model is None:
            self._model = load_forecast

        self._model = self._update_model_forecasts(load_forecast, now)

        min_soc = None
        battery = self.battery_capacity_remaining()
        available_capacity = self._capacity - (self._min_soc * self._capacity)
        for index, _ in self._model.iterrows():
            period = self._model.iloc[index]["period_start"].to_pydatetime()
            if period >= now:

                if (
                    self._in_between(
                        period.time(), self._eco_start_time, self._eco_end_time
                    )
                    and min_soc is None
                ):
                    _, _, _, min_soc = self._charge_totals(period, battery)

                if period.time() == self._eco_start_time:
                    # landed on the start of the eco period
                    dawn_charge, day_charge, total, min_soc = self._charge_totals(
                        period, battery
                    )
                    battery += max(0, total)
                    # store in dataframe for retrieval later
                    self._model.at[index, "charge_dawn"] = dawn_charge
                    self._model.at[index, "charge_day"] = day_charge
                elif (
                    self._in_between(
                        period.time(), self._eco_start_time, self._eco_end_time
                    )
                    and battery < min_soc
                ):
                    # hold SoC in off-peak period
                    battery = min_soc
                else:
                    delta = self._model.iloc[index]["delta"]
                    new_state = battery + delta
                    battery = max([0, min([available_capacity, new_state])])
                    if new_state <= 0 or new_state >= available_capacity:
                        # import (-) or excess (+)
                        self._model.at[index, "grid"] = delta
                    else:
                        # battery usage
                        self._model.at[index, "grid"] = 0

                self._model.at[index, "battery"] = battery

        self._ready = True

    def _charge_totals(self, period, battery):
        """Return charge totals for dawn/day"""
        # calculate start/end of the next peak period
        eco_start = period.replace(
            hour=self._eco_start_time.hour,
            minute=self._eco_start_time.minute,
            second=0,
            microsecond=0,
        )
        eco_end = self._next_eco_end_time(eco_start)
        next_eco_start = eco_start + timedelta(days=1)
        # grab all peak values
        peak = self._model[
            (self._model["period_start"] > eco_end)
            & (self._model["period_start"] < next_eco_start)
        ]
        # sum forecast and house load
        forecast_sum = peak.pv_estimate.sum()
        load_sum = peak.load.sum()
        dawn_load = self._dawn_load(eco_end)
        dawn_charge = self.dawn_charge_needs(dawn_load, battery)
        day_charge = self.day_charge_needs(forecast_sum, load_sum, battery)
        total = max([dawn_charge, day_charge])
        min_soc = battery + total
        _LOGGER.debug(
            f"Period: {period.date()} - EcoStart: {battery} MinSoC: {min_soc} Dawn: {dawn_charge} Day: {day_charge}"
        )

        return dawn_charge, day_charge, total, min_soc

    def _update_model_forecasts(self, load_forecast, now):
        # get all future values
        future = load_forecast[load_forecast["period_start"] > now]
        # keep original values including load, pv, grid etc
        hist = self._model[
            (self._model["period_start"] <= now)
            & (self._model["period_start"] > (now - timedelta(days=3)))
        ]
        # set global model
        return hist.append(future)

    def _in_between(self, now, start, end):
        """In between two times"""
        if start <= end:
            return start <= now < end
        else:  # over midnight e.g., 23:30-04:15
            return now >= start or now < end

    def _merge_dataframes(self, load, forecast):
        """Merge load and forecast dataframes"""
        load = load.groupby(load["time"]).mean()
        load["time"] = load.index.values

        # limit forecast values to future only
        forecast = forecast[forecast["date"] >= datetime.utcnow().date()]

        # reset indexes
        load.reset_index(drop=True, inplace=True)
        forecast.reset_index(drop=True, inplace=True)

        # merge load and forecast to produce a delta
        load_forecast = pd.merge(load, forecast, how="right", on=["time"])
        load_forecast["delta"] = load_forecast["pv_estimate"] - load_forecast["load"]

        load_forecast = load_forecast.reset_index(drop=True)
        load_forecast = load_forecast.sort_values(by="period_start")

        return load_forecast

    def state_at_eco_start(self) -> float:
        """State at eco end"""
        eco_time = self._next_eco_start_time().replace(second=0, microsecond=0)
        eco_time -= timedelta(minutes=1)
        return self._model[self._model["period_start"] == eco_time].battery.iloc[0]

    def dawn_charge(self):
        """Dawn charge required"""
        return self._charge_info().iloc[0].charge_dawn

    def day_charge(self):
        """Day charge required"""
        return self._charge_info().iloc[0].charge_day

    def _charge_info(self):
        """Charge info"""
        return self._model[self._model["period_start"] == self._next_eco_start_time()]

    def _dawn_load(self, eco_end_time) -> float:
        """Dawn load"""
        dawn_time = self._dawn_time(eco_end_time)

        dawn_load = self._model[
            (self._model["period_start"] > eco_end_time)
            & (self._model["period_start"] < dawn_time)
        ]

        load_sum = abs(dawn_load.delta.sum())

        return round(load_sum, 2)

    def _dawn_time(self, date: datetime) -> datetime:
        """Calculate dawn time"""
        filtered = self._model[self._model["date"] == date.date()]
        dawn = filtered[filtered["delta"] > 0]

        if len(dawn) == 0:
            # Solar never reaches house load... return mid-day
            return date.replace(hour=12, minute=0, second=0, microsecond=0)
        else:
            return dawn.iloc[0].period_start.to_pydatetime()

    def dawn_charge_needs(self, dawn_load, eco_start) -> float:
        """Dawn charge needs"""
        dawn_charge_needs = eco_start - dawn_load

        dawn_buffer = self._dawn_buffer - dawn_charge_needs

        ceiling = self.ceiling_charge_total(dawn_buffer, eco_start)

        return round(ceiling, 2)

    def day_charge_needs(
        self, forecast: float, house_load: float, eco_start: float
    ) -> float:
        """Day charge needs"""
        day_charge_needs = (eco_start - house_load) + forecast

        day_buffer_top_up = self._day_buffer - day_charge_needs

        ceiling = self.ceiling_charge_total(day_buffer_top_up, eco_start)

        return round(ceiling, 2)

    def ceiling_charge_total(self, charge_total: float, eco_start: float) -> float:
        """Ceiling total charge"""
        available_capacity = round(
            self._capacity - (self._min_soc * self._capacity) - eco_start,
            2,
        )

        return min(available_capacity, charge_total)

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

    def battery_depleted_time(self) -> datetime:
        """Time battery capacity is 0"""

        if self.battery_capacity_remaining() == 0:
            # battery is already empty, prevent constant time updates and set sensor to unknown
            return None

        battery_depleted = self._model[
            (self._model["battery"] == 0)
            & (self._model["period_start"] > datetime.now().astimezone())
        ]

        if len(battery_depleted) == 0:
            # battery runs past our model, return the last result
            return self._model.iloc[-1].period_start

        return self._model.iloc[battery_depleted["period_start"].idxmin()].period_start

    def peak_grid_import(self) -> float:
        """Grid usage required to next eco start"""
        eco_start = self._next_eco_start_time()

        grid_use = self._model[
            (self._model["grid"] < 0) & (self._model["period_start"] < eco_start)
        ]

        if len(grid_use) == 0:
            return 0

        return round(abs(grid_use.grid.sum()), 2)

    def peak_grid_export(self) -> float:
        """Grid usage required to next eco start"""
        eco_start = self._next_eco_start_time()

        grid_export = self._model[
            (self._model["grid"] > 0) & (self._model["period_start"] < eco_start)
        ]

        if len(grid_export) == 0:
            return 0

        return round(grid_export.grid.sum(), 2)

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

    def _next_eco_end_time(self, period) -> datetime:
        """Next eco end time"""
        eco_end = period.replace(
            hour=self._eco_end_time.hour,
            minute=self._eco_end_time.minute,
            second=0,
            microsecond=0,
        )
        if period > eco_end:
            eco_end += timedelta(days=1)

        return eco_end
