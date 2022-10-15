"""Energy platform."""
from __future__ import annotations

import logging

from homeassistant.core import HomeAssistant

from . import ForecastController
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_get_solar_forecast(hass: HomeAssistant, config_entry_id: str):
    """Get solar forecast for a config entry ID."""

    controller: ForecastController = hass.data[DOMAIN][config_entry_id]["controllers"][
        "forecast"
    ]

    if controller is None:
        return None

    try:
        energy = controller.energy()
        energy_dict = dict(zip(energy.period_start_iso, energy.pv_watts))

        return {"wh_hours": energy_dict}

    except Exception:
        return None
