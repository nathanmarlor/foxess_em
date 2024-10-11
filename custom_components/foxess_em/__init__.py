"""
Custom integration to integrate FoxESS Energy Management with Home Assistant.

For more details about this integration, please refer to
https://github.com/nathanmarlor/foxess_em
"""

import asyncio
import copy
from datetime import time
import logging


from homeassistant.config_entries import ConfigEntry, ConfigEntryAuthFailed
from homeassistant.const import (
    MAJOR_VERSION as HA_MAJOR_VERSION,
    MINOR_VERSION as HA_MINOR_VERSION,
)
from homeassistant.core import Config, HomeAssistant
from homeassistant.helpers import config_validation
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from custom_components.foxess_em.battery.schedule import Schedule
from custom_components.foxess_em.fox.fox_modbus import FoxModbus
from custom_components.foxess_em.fox.fox_modbus_service import FoxModbuservice
from custom_components.foxess_em.util.peak_period_util import PeakPeriodUtils

from .average.average_controller import AverageController
from .battery.battery_controller import BatteryController
from .charge.charge_service import ChargeService
from .config_flow import BatteryManagerFlowHandler
from .const import (
    AUX_POWER,
    BATTERY_CAPACITY,
    BATTERY_SOC,
    BATTERY_VOLTS,
    CHARGE_AMPS,
    CONNECTION_TYPE,
    DAWN_BUFFER,
    DAY_BUFFER,
    DOMAIN,
    ECO_END_TIME,
    ECO_START_TIME,
    FOX_API_KEY,
    FOX_CLOUD,
    FOX_MODBUS_HOST,
    FOX_MODBUS_PORT,
    FOX_MODBUS_SERIAL,
    FOX_MODBUS_SLAVE,
    FOX_MODBUS_TCP,
    HOUSE_POWER,
    MIN_SOC,
    PLATFORMS,
    SOLCAST_API_KEY,
    SOLCAST_URL,
    STARTUP_MESSAGE,
    Connection,
)
from .forecast.forecast_controller import ForecastController
from .forecast.solcast_api import SolcastApiClient
from .fox.fox_cloud_api import FoxCloudApiClient
from .fox.fox_cloud_service import FoxCloudService

_LOGGER: logging.Logger = logging.getLogger(__package__)

CONFIG_SCHEMA = config_validation.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: Config):
    """Set up this integration using YAML is not supported."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up this integration using UI."""
    if hass.data.get(DOMAIN) is None:
        hass.data.setdefault(DOMAIN, {})
        _LOGGER.info(STARTUP_MESSAGE)

    # Check FoxESS API Key before settings up the other platforms to prevent those being setup if it
    # fails, which will prevent setup working when the FoxESS API key is fixed.
    entry_options = copy.deepcopy(dict(entry.options))
    entry_data = copy.deepcopy(dict(entry.data))
    _LOGGER.debug(f"Options {entry.options}")
    _LOGGER.debug(f"Data {entry.data}")

    if entry_options != entry_data:
        # overwrite data with options
        entry_data = copy.deepcopy(dict(entry.options))
        _LOGGER.info("Config has been updated")
    _LOGGER.debug(f"_Data {entry_data}")


    connection_type = entry_data.get(CONNECTION_TYPE, FOX_MODBUS_TCP)
    fox_api_key = entry_data.get(FOX_API_KEY)
    if connection_type == FOX_CLOUD:
        if not fox_api_key:
            raise ConfigEntryAuthFailed(
                "FoxESSCloud must now be accessed vi API Keys. Please reconfigure."
            )


    solcast_api_key = entry_data.get(SOLCAST_API_KEY)

    eco_start_time = time.fromisoformat(entry_data.get(ECO_START_TIME))
    eco_end_time = time.fromisoformat(entry_data.get(ECO_END_TIME))
    house_power = entry_data.get(HOUSE_POWER)
    battery_soc = entry_data.get(BATTERY_SOC)
    aux_power = entry_data.get(AUX_POWER)
    user_min_soc = entry_data.get(MIN_SOC)
    capacity = entry_data.get(BATTERY_CAPACITY)
    dawn_buffer = entry_data.get(DAWN_BUFFER)
    day_buffer = entry_data.get(DAY_BUFFER)
    # Added for 1.6.1
    charge_amps = entry_data.get(CHARGE_AMPS, 18)
    battery_volts = entry_data.get(BATTERY_VOLTS, 208)
    # Added for 1.7.0
    fox_modbus_host = entry_data.get(FOX_MODBUS_HOST, "")
    fox_modbus_port = entry_data.get(FOX_MODBUS_PORT, 502)
    fox_modbus_slave = entry_data.get(FOX_MODBUS_SLAVE, 247)

    session = async_get_clientsession(hass)
    solcast_client = SolcastApiClient(solcast_api_key, SOLCAST_URL, session)

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

    _LOGGER.debug(f"Initialising {connection_type} service")
    if connection_type == FOX_CLOUD:
        cloud_client = FoxCloudApiClient(session, fox_api_key)
        fox_service = FoxCloudService(
            hass, cloud_client, eco_start_time, eco_end_time, user_min_soc
        )
    else:
        params = {CONNECTION_TYPE: connection_type}
        if connection_type == FOX_MODBUS_TCP:
            params.update({"host": fox_modbus_host, "port": fox_modbus_port})
        else:
            params.update({"port": fox_modbus_host, "baudrate": 9600})
        modbus_client = FoxModbus(hass, params)
        fox_service = FoxModbuservice(
            hass,
            modbus_client,
            fox_modbus_slave,
            eco_start_time,
            eco_end_time,
            user_min_soc,
        )

    charge_service = ChargeService(
        hass,
        battery_controller,
        forecast_controller,
        fox_service,
        peak_utils,
        eco_start_time,
        eco_end_time,
        battery_soc,
        user_min_soc,
        charge_amps,
        battery_volts,
    )

    hass.data[DOMAIN][entry.entry_id] = {
        "controllers": {
            "average": average_controller,
            "battery": battery_controller,
            "forecast": forecast_controller,
            "charge": charge_service,
        },
        "config": {
            "connection": (
                Connection.MODBUS
                if (connection_type in (FOX_MODBUS_TCP, FOX_MODBUS_SERIAL))
                else Connection.CLOUD
            )
        },
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

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
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


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Handle migration from earlier configuration options."""
    version = config_entry.version

    if version == 1:
        data = dict(config_entry.data)
        if data.get(CONNECTION_TYPE) == FOX_CLOUD:
            # Migrate from username/password to API keys.
            if not data.get(FOX_API_KEY):
                _LOGGER.error(
                    "FoxESS Energy Management can no longer access foxesscloud.com using a username and password.\r\nPlease reconfigure using API keys."
                )

        # Migrate the config to the new version. There are no automatically migratable config
        # changes and in retrospect, the major version number shouldn't have changed to 2 when
        # adding the API key, but it's done now so just migrate to version 2 and fix up the config
        # else where.
        if HA_MAJOR_VERSION > 2024 or (
            HA_MAJOR_VERSION == 2024 and HA_MINOR_VERSION >= 3
        ):
            # 2024.3 disallows direct modification of the config_entry when migrating and adds
            # version parameters to async_update_entry.
            hass.config_entries.async_update_entry(
                config_entry,
                data=data,
                version=BatteryManagerFlowHandler.VERSION,
            )
        else:
            config_entry.version = BatteryManagerFlowHandler.VERSION

    return True
