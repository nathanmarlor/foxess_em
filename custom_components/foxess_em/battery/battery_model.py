"""Battery model"""

from datetime import datetime, time, timedelta
import json
import logging

from homeassistant.core import HomeAssistant
import pandas as pd

from custom_components.foxess_em.battery.battery_util import BatteryUtils
from custom_components.foxess_em.battery.schedule import Schedule
from custom_components.foxess_em.util.peak_period_util import PeakPeriodUtils

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
        eco_start_time: time,
        battery_soc: str,
        schedule: Schedule,
        peak_utils: PeakPeriodUtils,
        battery_utils: BatteryUtils,
    ) -> None:
        self._hass = hass
        self._model = None
        self._ready = False
        self._min_soc = min_soc
        self._capacity = capacity
        self._dawn_buffer = dawn_buffer
        self._day_buffer = day_buffer
        self._eco_start_time = eco_start_time
        self._battery_soc = battery_soc
        self._schedule = schedule
        self._peak_utils = peak_utils
        self._battery_utils = battery_utils

    def ready(self) -> bool:
        """Model status"""
        return self._ready

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

        if self._model is None:
            self._model = load_forecast

        load_forecast = load_forecast.sort_values(by="period_start")

        future = load_forecast[load_forecast["period_start"] > now]

        available_capacity = self._capacity - (self._min_soc * self._capacity)

        battery = self._battery_capacity_remaining()
        last_schedule = self._schedule.get(self._peak_utils.last_eco_start(now))
        if last_schedule is not None:
            # grab the min soc from the last eco start calc, including boost
            min_soc = last_schedule["min_soc"]
        elif self._peak_utils.in_peak(now.time()):
            # no history and in an eco period, recalulate without knowing boost
            _, min_soc = self._charge_totals(load_forecast, now, battery)

        for index, _ in future.iterrows():
            period = (
                load_forecast.iloc[index]["period_start"].to_pydatetime().astimezone()
            )
            if period.time() == self._eco_start_time:
                # landed on the start of the eco period
                boost = self._get_total_additional_charge(period)
                total, min_soc = self._charge_totals(
                    load_forecast, period, battery, boost
                )
                battery += total
            elif self._peak_utils.in_peak(period.time()) and battery < min_soc:
                # hold SoC in off-peak period
                battery = min_soc
            else:
                delta = load_forecast.iloc[index]["delta"]
                new_state = battery + delta
                battery = max([0, min([available_capacity, new_state])])
                if new_state <= 0 or new_state >= available_capacity:
                    # import (-) or excess (+)
                    load_forecast.at[index, "grid"] = delta
                else:
                    # battery usage
                    load_forecast.at[index, "grid"] = 0
            load_forecast.at[index, "battery"] = battery

        for index, _ in future.iterrows():
            period = (
                load_forecast.iloc[index]["period_start"].to_pydatetime().astimezone()
            )
            if period.time() == self._eco_start_time:
                self._add_metadata(load_forecast, period)

        self._model = self._update_model_forecasts(load_forecast, now)
        self._ready = True

    def _charge_totals(
        self,
        model: pd.DataFrame,
        period: datetime,
        battery: float,
        boost: float = 0,
    ):
        """Return charge totals for dawn/day"""
        # calculate start/end of the next peak period
        eco_start = period.replace(
            hour=self._eco_start_time.hour,
            minute=self._eco_start_time.minute,
            second=0,
            microsecond=0,
        )
        eco_end_time = self._peak_utils.next_eco_end(eco_start)
        next_eco_start = eco_start + timedelta(days=1)
        # grab all peak values
        peak = model[
            (model["period_start"] > eco_end_time)
            & (model["period_start"] < next_eco_start)
        ]

        # sum forecast and house load
        forecast_sum = peak.pv_estimate.sum()
        load_sum = peak.load.sum()
        dawn_load = self._dawn_load(model, eco_end_time)
        dawn_charge = self._dawn_charge_needs(dawn_load)
        day_charge = self._day_charge_needs(forecast_sum, load_sum)
        max_charge = self._battery_utils.ceiling_charge_total(
            max([dawn_charge, day_charge])
        )
        min_soc = (
            max_charge
            if boost == 0
            else self._battery_utils.ceiling_charge_total(
                max([battery, max_charge]) + boost
            )
        )
        total = self._battery_utils.ceiling_charge_total(max([0, min_soc - battery]))
        # store in dataframe for retrieval later
        self._schedule.upsert(
            eco_start,
            {
                "eco_start": eco_start,
                "eco_end": self._peak_utils.next_eco_end(eco_start),
                "battery": battery,
                "load": load_sum,
                "forecast": forecast_sum,
                "dawn": dawn_charge,
                "day": day_charge,
                "total": total,
                "min_soc": min_soc,
            },
        )

        return total, min_soc

    def _add_metadata(self, model: pd.DataFrame, period: datetime):
        """Added metadata - i.e. grid import/export"""
        # calculate start/end of the next peak period
        eco_start = period.replace(
            hour=self._eco_start_time.hour,
            minute=self._eco_start_time.minute,
            second=0,
            microsecond=0,
        )
        eco_end_time = self._peak_utils.next_eco_end(eco_start)
        next_eco_start = eco_start + timedelta(days=1)
        # grab all peak values
        peak = model[
            (model["period_start"] > eco_end_time)
            & (model["period_start"] < next_eco_start)
        ]

        # metadata - import/export
        grid_import = abs(peak[(peak["grid"] < 0)].grid.sum())
        grid_export = peak[(peak["grid"] > 0)].grid.sum()

        self._schedule.upsert(
            eco_start,
            {"import": grid_import, "export": grid_export},
        )

    def next_dawn_time(self) -> datetime:
        """Calculate dawn time"""
        now = datetime.now().astimezone()

        dawn_today = self._dawn_time(self._model, now)
        dawn_tomorrow = self._dawn_time(self._model, now + timedelta(days=1))

        if now > dawn_today:
            return dawn_tomorrow
        else:
            return dawn_today

    def todays_dawn_time(self) -> datetime:
        """Calculate dawn time"""
        now = datetime.now().astimezone()
        return self._dawn_time(self._model, now)

    def battery_depleted_time(self) -> datetime:
        """Time battery capacity is 0"""

        if self._battery_capacity_remaining() <= 0:
            # battery is already empty, prevent constant time updates and set sensor to unknown
            return None

        battery_depleted = self._model[
            (self._model["battery"] == 0)
            & (self._model["period_start"] > datetime.now().astimezone())
        ]

        if len(battery_depleted) == 0:
            # battery runs past our model, return the last result
            return self._model.iloc[-1].period_start

        return battery_depleted.iloc[0].period_start

    def peak_grid_import(self) -> float:
        """Grid usage required to next eco start"""
        now = datetime.now().astimezone()
        eco_start = self._peak_utils.next_eco_start()

        grid_use = self._model[
            (self._model["grid"] < 0)
            & (self._model["period_start"] > now)
            & (self._model["period_start"] < eco_start)
        ]

        if len(grid_use) == 0:
            return 0

        return round(abs(grid_use.grid.sum()), 2)

    def peak_grid_export(self) -> float:
        """Grid usage required to next eco start"""
        now = datetime.now().astimezone()
        eco_start = self._peak_utils.next_eco_start()

        grid_export = self._model[
            (self._model["grid"] > 0)
            & (self._model["period_start"] > now)
            & (self._model["period_start"] < eco_start)
        ]

        if len(grid_export) == 0:
            return 0

        return round(grid_export.grid.sum(), 2)

    def _battery_capacity_remaining(self) -> float:
        """Usable capacity remaining"""
        battery_state = self._hass.states.get(self._battery_soc)
        if battery_state is None:
            raise NoDataError("Battery state is invalid")
        if battery_state.state in ["unknown", "unavailable"]:
            raise NoDataError("Battery state is unknown")

        battery_soc = int(battery_state.state)
        battery_capacity = (battery_soc / 100) * self._capacity

        return battery_capacity - (self._min_soc * self._capacity)

    def _update_model_forecasts(self, future: pd.DataFrame, now: datetime):
        # keep original values including load, pv, grid etc
        hist = self._model[
            (self._model["period_start"] <= now)
            & (self._model["period_start"] > (now - timedelta(days=3)))
        ]
        # set global model
        return pd.concat([hist, future])

    def _get_total_additional_charge(self, period: datetime):
        """Get all additional charge"""
        boost = self._get_boost(period, "boost_status")
        full = self._get_boost(period, "full_status")

        return max([boost, full])

    def _get_boost(self, index: datetime, boost_type: str) -> float:
        """Retrieve schedule item"""
        schedule = self._schedule.get(index)
        if schedule is not None and boost_type in schedule:
            return schedule[boost_type]

        return 0

    def _merge_dataframes(self, load: pd.DataFrame, forecast: pd.DataFrame):
        """Merge load and forecast dataframes"""
        load = load.groupby(load["time"]).mean()
        load["time"] = load.index.values

        # reset indexes
        load.reset_index(drop=True, inplace=True)
        forecast.reset_index(drop=True, inplace=True)

        # merge load and forecast to produce a delta
        load_forecast = pd.merge(load, forecast, how="right", on=["time"])
        load_forecast["delta"] = load_forecast["pv_estimate"] - load_forecast["load"]

        load_forecast.reset_index(drop=True, inplace=True)

        return load_forecast

    def _dawn_load(self, model: pd.DataFrame, eco_end_time: datetime) -> float:
        """Dawn load"""
        dawn_time = self._dawn_time(model, eco_end_time)

        dawn_load = model[
            (model["period_start"] > eco_end_time) & (model["period_start"] < dawn_time)
        ]

        load_sum = abs(dawn_load.delta.sum())

        return round(load_sum, 2)

    def _dawn_time(self, model: pd.DataFrame, date: datetime) -> datetime:
        """Calculate dawn time"""
        filtered = model[model["date"] == date.date()]
        dawn = filtered[(filtered["delta"] > 0) & (filtered["load"] > 0)]

        if len(dawn) == 0:
            # Solar never reaches house load... return mid-day
            return date.replace(hour=12, minute=0, second=0, microsecond=0)
        else:
            return dawn.iloc[0].period_start.to_pydatetime()

    def _dawn_charge_needs(self, dawn_load: float) -> float:
        """Dawn charge needs"""
        return round(max([0, dawn_load + self._dawn_buffer]), 2)

    def _day_charge_needs(self, forecast: float, house_load: float) -> float:
        """Day charge needs"""
        return round(max([0, (house_load + self._day_buffer) - forecast]), 2)
