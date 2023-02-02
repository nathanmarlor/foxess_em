"""
Custom integration to integrate FoxESS Energy Management with Home Assistant.

For more details about this integration, please refer to
https://github.com/nathanmarlor/foxess_em
"""
import asyncio
import logging
from datetime import time

from custom_components.foxess_em.battery.schedule import Schedule
from custom_components.foxess_em.util.peak_period_util import PeakPeriodUtils
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Config
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .average.average_controller import AverageController
from .battery.battery_controller import BatteryController
from .charge.charge_service import ChargeService
from .const import AUX_POWER
from .const import BATTERY_CAPACITY
from .const import BATTERY_SOC
from .const import CHARGE_RATE
from .const import DAWN_BUFFER
from .const import DAY_BUFFER
from .const import DOMAIN
from .const import ECO_END_TIME
from .const import ECO_START_TIME
from .const import FOX_PASSWORD
from .const import FOX_USERNAME
from .const import HOUSE_POWER
from .const import MIN_SOC
from .const import PLATFORMS
from .const import SOLCAST_API_KEY
from .const import SOLCAST_URL
from .const import STARTUP_MESSAGE
from .forecast.forecast_controller import ForecastController
from .forecast.solcast_api import SolcastApiClient
from .fox.fox_api import FoxApiClient
from .fox.fox_cloud_service import FoxCloudService

_LOGGER: logging.Logger = logging.getLogger(__package__)


async def async_setup(hass: HomeAssistant, config: Config):
    """Set up this integration using YAML is not supported."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up this integration using UI."""
    if hass.data.get(DOMAIN) is None:
        hass.data.setdefault(DOMAIN, {})
        _LOGGER.info(STARTUP_MESSAGE)

    for platform in PLATFORMS:
        if entry.options.get(platform, True):
            hass.async_add_job(
                hass.config_entries.async_forward_entry_setup(entry, platform)
            )

    if len(entry.options) > 0:
        # overwrite data with options
        entry.data = entry.options

    solcast_api_key = entry.data.get(SOLCAST_API_KEY)
    fox_username = entry.data.get(FOX_USERNAME)
    fox_password = entry.data.get(FOX_PASSWORD)
    eco_start_time = time.fromisoformat(entry.data.get(ECO_START_TIME))
    eco_end_time = time.fromisoformat(entry.data.get(ECO_END_TIME))
    house_power = entry.data.get(HOUSE_POWER)
    battery_soc = entry.data.get(BATTERY_SOC)
    aux_power = entry.data.get(AUX_POWER)
    user_min_soc = entry.data.get(MIN_SOC)
    capacity = entry.data.get(BATTERY_CAPACITY)
    dawn_buffer = entry.data.get(DAWN_BUFFER)
    day_buffer = entry.data.get(DAY_BUFFER)
    # Added for 1.6.1
    charge_rate = entry.data.get(CHARGE_RATE, 18)

    session = async_get_clientsession(hass)
    solcast_client = SolcastApiClient(solcast_api_key, SOLCAST_URL, session)

    fox_client = FoxApiClient(session, fox_username, fox_password)

    # Initialise controllers and services
    peak_utils = PeakPeriodUtils(eco_start_time, eco_end_time)

    forecast_controller = ForecastController(hass, solcast_client)
    average_controller = AverageController(
        hass, eco_start_time, eco_end_time, house_power, aux_power
    )
    schedule = Schedule(hass)
    battery_controller = BatteryController(
        hass,
        forecast_controller,
        average_controller,
        user_min_soc,
        capacity,
        dawn_buffer,
        day_buffer,
        eco_start_time,
        battery_soc,
        schedule,
        peak_utils,
    )
    fox_service = FoxCloudService(
        hass, fox_client, eco_start_time, eco_end_time, user_min_soc
    )
    charge_service = ChargeService(
        hass,
        battery_controller,
        forecast_controller,
        fox_service,
        eco_start_time,
        eco_end_time,
        battery_soc,
        user_min_soc,
        charge_rate,
    )

    hass.data[DOMAIN][entry.entry_id] = {
        "controllers": {
            "average": average_controller,
            "battery": battery_controller,
            "forecast": forecast_controller,
            "charge": charge_service,
        }
    }

    # Add callbacks into battery controller for updates
    forecast_controller.add_update_listener(battery_controller)
    average_controller.add_update_listener(battery_controller)

    hass.services.async_register(
        DOMAIN, "start_force_charge_now", fox_service.start_force_charge_now
    )
    hass.services.async_register(
        DOMAIN, "start_force_charge_off_peak", fox_service.start_force_charge_off_peak
    )
    hass.services.async_register(
        DOMAIN, "stop_force_charge", fox_service.stop_force_charge
    )
    hass.services.async_register(
        DOMAIN, "clear_schedule", battery_controller.clear_schedule
    )

    hass.data[DOMAIN][entry.entry_id]["unload"] = entry.add_update_listener(
        async_reload_entry
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Handle removal of an entry."""
    unloaded = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, platform)
                for platform in PLATFORMS
            ]
        )
    )

    if unloaded:
        controllers = hass.data[DOMAIN][entry.entry_id]["controllers"]
        for controller in controllers.values():
            controller.unload()

        hass.data[DOMAIN][entry.entry_id]["unload"]()
        hass.data[DOMAIN].pop(entry.entry_id)

    return unloaded


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)


async def options_update_listener(hass: HomeAssistant, config_entry: ConfigEntry):
    """Handle options update."""
    await hass.config_entries.async_reload(config_entry.entry_id)
