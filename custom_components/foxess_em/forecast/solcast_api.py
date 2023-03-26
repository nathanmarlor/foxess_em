"""Sample API Client."""
import logging
from datetime import timedelta
from typing import Any

import aiohttp
import async_timeout
import dateutil.parser

from ..util.exceptions import NoDataError

_TIMEOUT = 20

_LOGGER: logging.Logger = logging.getLogger(__package__)


class SolcastApiClient:
    """API client"""

    def __init__(
        self,
        solcast_api_key: str,
        solcast_url: str,
        session: aiohttp.ClientSession,
    ) -> None:
        """Sample API Client."""
        self._solcast_api_key = solcast_api_key
        self._solcast_url = solcast_url
        self._session = session

    async def async_get_api_calls(self) -> list[str]:
        """Return API information"""

        _LOGGER.debug("Retrieving API call status")
        api_status = await self._fetch_data(
            solcast_url=f"{self._solcast_url}/json/reply/GetUserDailyLimit",
            api_key=self._solcast_api_key,
        )

        return api_status

    async def async_get_sites(self) -> list[str]:
        """Return available sites"""

        _LOGGER.debug("Retrieving available sites")
        sites = await self._fetch_data(
            solcast_url=f"{self._solcast_url}/rooftop_sites",
            api_key=self._solcast_api_key,
        )

        return sites

    async def async_get_data(self, site_id: str) -> dict:
        """Get data from the API."""

        _LOGGER.debug(f"Retrieving history data for site: {site_id}")
        history = await self._fetch_data(
            api_key=self._solcast_api_key,
            solcast_url=f"{self._solcast_url}/rooftop_sites/{site_id}/estimated_actuals",
        )

        _LOGGER.debug(f"Retrieving forecast data for site: {site_id}")
        live = await self._fetch_data(
            api_key=self._solcast_api_key,
            solcast_url=f"{self._solcast_url}/rooftop_sites/{site_id}/forecasts",
        )

        if (history is None) | (live is None):
            raise NoDataError("Forecast data could not be processed")

        history_estimates = [
            {
                "period_start": dateutil.parser.isoparse(forecast["period_end"])
                - timedelta(minutes=30),
                "period_end": dateutil.parser.isoparse(forecast["period_end"]),
                "pv_estimate": forecast["pv_estimate"],
            }
            for forecast in history["estimated_actuals"]
        ]

        live_estimates = [
            {
                "period_start": dateutil.parser.isoparse(forecast["period_end"])
                - timedelta(minutes=30),
                "period_end": dateutil.parser.isoparse(forecast["period_end"]),
                "pv_estimate": forecast["pv_estimate"],
            }
            for forecast in live["forecasts"]
        ]

        return history_estimates[1:] + live_estimates

    async def _fetch_data(
        self, api_key: str, solcast_url: str, hours=120
    ) -> dict[str, Any]:
        """fetch data via the Solcast API."""

        try:
            params = {"format": "json", "api_key": api_key, "hours": hours}

            async with async_timeout.timeout(_TIMEOUT):
                response = await self._session.get(
                    solcast_url,
                    params=params,
                )

                status = response.status

            if status == 200:
                return await response.json(content_type=None)
            else:
                self._log_status(status)
        except Exception as ex:
            _LOGGER.error("Solcast API fetch error: %s", ex)

    def _log_status(self, status: int) -> None:
        """Processes status code returned from Solcast"""
        if status == 429:
            _LOGGER.error("Solcast API allowed polling limit exceeded")
        elif status == 400:
            _LOGGER.error(
                "Solcast rooftop site missing capacity, please specify capacity or provide historic data for tuning."
            )
        elif status == 404:
            _LOGGER.error("Solcast rooftop site cannot be found or is not accessible.")
