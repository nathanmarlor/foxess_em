"""Forecast model"""
import logging
from datetime import datetime
from datetime import timedelta

import pandas as pd

from ..forecast.solcast_api import SolcastApiClient
from ..util.exceptions import NoDataError

_LOGGER: logging.Logger = logging.getLogger(__package__)


class ForecastModel:
    """Forecast model"""

    def __init__(self, api: SolcastApiClient) -> None:
        """Solcast API"""
        self._resampled = {}
        self._api = api
        self._ready = False

    def ready(self):
        """Model status"""
        return self._ready

    async def refresh(self) -> dict:
        """Get data from the API."""

        data = await self._api.async_get_data()

        self._resampled = self._resample(data)

        self._ready = True

    def resample_data(self):
        """Return resampled data"""
        if len(self._resampled) == 0:
            raise NoDataError("No forecast data available")
        return self._resampled

    def total_kwh_forecast_today(self) -> int:
        """Total forecast today"""
        date_now = datetime.now().astimezone()
        f_df = self._resampled
        filtered = f_df[f_df["date"] == date_now.date()]

        return round(filtered.pv_estimate.sum(), 2)

    def total_kwh_forecast_tomorrow(self) -> int:
        """Total forecast tomorrow"""
        date_tomorrow = datetime.now().astimezone() + timedelta(days=1)
        f_df = self._resampled
        filtered = f_df[f_df["date"] == date_tomorrow.date()]

        return round(filtered.pv_estimate.sum(), 2)

    def total_kwh_forecast_today_remaining(self):
        """Return Remaining Forecasts data for today"""
        date_now = datetime.now().astimezone()
        forecast = self._resampled
        forecast = forecast[
            (forecast["period_start"] >= date_now)
            & (forecast["date"] == date_now.date())
        ]

        return round(forecast.pv_estimate.sum(), 2)

    def energy(self):
        """Return energy"""
        return self._resampled

    def _resample(self, values):
        """Resample values"""
        df = pd.DataFrame.from_dict(values)

        df = df.set_index("period_start").resample("1Min").mean().interpolate("linear")
        df["period_start"] = pd.to_datetime(df.index.values, utc=True)
        df["period_start_iso"] = df["period_start"].map(lambda x: x.isoformat())
        df["pv_estimate"] = df["pv_estimate"] / 60
        df["pv_watts"] = df["pv_estimate"] * 1000
        df["time"] = df.index.time
        df["date"] = df.index.date

        df = df.sort_index()

        return df
