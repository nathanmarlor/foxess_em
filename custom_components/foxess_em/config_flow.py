"""Adds config flow for foxess_em."""

import datetime
import logging
from typing import Any

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv, selector
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.selector import selector as sel
from pymodbus.exceptions import ModbusException
import voluptuous as vol

from custom_components.foxess_em.fox.fox_modbus import FoxModbus

from ..foxess_em.const import DAWN_BUFFER, DAY_BUFFER, MIN_SOC
from .const import (
    AUX_POWER,
    BATTERY_CAPACITY,
    BATTERY_SOC,
    BATTERY_VOLTS,
    CHARGE_AMPS,
    CONNECTION_TYPE,
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
    SOLCAST_API_KEY,
    SOLCAST_URL,
)
from .forecast.solcast_api import SolcastApiClient
from .fox.fox_cloud_api import FoxCloudApiClient
from .fox.fox_cloud_service import FoxCloudService
from .fox.fox_modbus_service import FoxModbuservice

_TITLE = "FoxESS - Energy Management"

_LOGGER = logging.getLogger(__name__)


class BatteryManagerFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for foxess_em."""

    VERSION = 2
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    reauth_entry: ConfigEntry | None = None

    def __init__(self, config=None) -> None:
        """Initialize."""
        self._errors = {}
        self._config = config
        self._user_input = {}
        if config is None:
            self._data = dict()
            self._options = dict()
        else:
            self._data = dict(self._config.data)
            self._options = dict(self._config.options)

        self._solcast_schema = vol.Schema(
            {
                vol.Required(
                    SOLCAST_API_KEY,
                    default=self._data.get(SOLCAST_API_KEY, ""),
                ): cv.string,
            }
        )

        self._inverter_connection_schema = vol.Schema(
            {
                vol.Required(CONNECTION_TYPE, default=FOX_MODBUS_TCP): sel(
                    {
                        "select": {
                            "options": [FOX_MODBUS_TCP, FOX_MODBUS_SERIAL, FOX_CLOUD]
                        }
                    }
                )
            }
        )

        self._modbus_tcp_schema = vol.Schema(
            {
                vol.Required(
                    FOX_MODBUS_HOST,
                    default=self._data.get(FOX_MODBUS_HOST, "192.168.x.x"),
                ): cv.string,
                vol.Required(
                    FOX_MODBUS_PORT,
                    default=502,
                ): int,
                vol.Required(
                    FOX_MODBUS_SLAVE,
                    default=247,
                ): int,
            }
        )

        self._modbus_serial_schema = vol.Schema(
            {
                vol.Required(
                    FOX_MODBUS_HOST,
                    default=self._data.get(FOX_MODBUS_HOST, "/dev/ttyUSB0"),
                ): cv.string,
                vol.Required(
                    FOX_MODBUS_SLAVE,
                    default=self._data.get(FOX_MODBUS_SLAVE, 247),
                ): int,
            }
        )

        self._cloud_schema = vol.Schema(
            {
                vol.Required(
                    FOX_API_KEY,
                    default=self._data.get(FOX_API_KEY, ""),
                ): str,
            }
        )

        self._battery_schema = vol.Schema(
            {
                vol.Required(
                    ECO_START_TIME,
                    default=self._data.get(
                        ECO_START_TIME, datetime.time(0, 30).isoformat()
                    ),
                ): str,
                vol.Required(
                    ECO_END_TIME,
                    default=self._data.get(
                        ECO_END_TIME, datetime.time(4, 30).isoformat()
                    ),
                ): str,
                vol.Required(
                    DAWN_BUFFER, default=float(self._data.get(DAWN_BUFFER, 1))
                ): vol.All(vol.Coerce(float), vol.Range(min=0, max=50)),
                vol.Required(
                    DAY_BUFFER, default=self._data.get(DAY_BUFFER, 2)
                ): vol.All(vol.Coerce(float), vol.Range(min=0, max=50)),
                vol.Required(
                    BATTERY_CAPACITY, default=self._data.get(BATTERY_CAPACITY, 10.4)
                ): vol.Coerce(float),
                vol.Required(
                    MIN_SOC,
                    default=self._data.get(MIN_SOC, 0.11) * 100,
                ): vol.All(vol.Coerce(float), vol.Range(min=10, max=99)),
            }
        )

        self._modbus_battery_schema = {
            vol.Required(
                CHARGE_AMPS,
                default=self._data.get(CHARGE_AMPS, 18),
            ): vol.All(vol.Coerce(float), vol.Range(min=1, max=99)),
            vol.Required(
                BATTERY_VOLTS,
                default=self._data.get(BATTERY_VOLTS, 208),
            ): vol.All(vol.Coerce(float), vol.Range(min=1, max=2000)),
        }

        self._power_schema = vol.Schema(
            {
                vol.Required(
                    BATTERY_SOC,
                    default=self._data.get(BATTERY_SOC, "sensor.battery_soc"),
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor", multiple=False)
                ),
                vol.Required(
                    HOUSE_POWER,
                    default=self._data.get(HOUSE_POWER, "sensor.load_power"),
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor", multiple=False)
                ),
                vol.Optional(
                    AUX_POWER,
                    default=self._data.get(AUX_POWER, []),
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor", multiple=True)
                ),
            }
        )

    async def async_step_reauth(self, user_input=None):
        """Perform reauth upon an API authentication error."""
        self.reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_reauth_fox_api_key()

    async def async_step_reauth_fox_api_key(self, user_input=None):
        """Ask user to add their API Key."""
        if user_input is not None:
            fox_valid = await self._test_fox_cloud(user_input[FOX_API_KEY])
            if fox_valid:
                self._errors["base"] = None
                data = dict(self.reauth_entry.data)
                options = dict(self.reauth_entry.data)
                data.update(user_input)
                options.update(user_input)
                return self.async_update_reload_and_abort(
                    self.reauth_entry,
                    data=data,
                    options=options,
                )
            else:
                self._errors["base"] = "fox_error"

        return self.async_show_form(
            step_id="reauth_fox_api_key",
            data_schema=self._cloud_schema,
            errors=self._errors,
        )

    async def async_step_init(self, user_input: dict[str, Any] = None):
        """Handle a flow initialized by the user."""
        self._errors = {}

        return await self.async_step_solcast(user_input)

    async def async_step_user(self, user_input: dict[str, Any] = None):
        """Handle a flow initialized by the user."""
        self._errors = {}

        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        return await self.async_step_solcast(user_input)

    async def async_step_solcast(self, user_input: dict[str, Any] = None):
        """Handle a flow initialized by the user."""
        if user_input is not None:
            solcast_valid = await self._test_solcast(
                user_input[SOLCAST_API_KEY], SOLCAST_URL
            )
            if solcast_valid:
                self._errors["base"] = None
                self._user_input.update(user_input)
                return await self.async_step_inverter()
            else:
                self._errors["base"] = "solcast_auth"

        return self.async_show_form(
            step_id="user", data_schema=self._solcast_schema, errors=self._errors
        )

    async def async_step_inverter(self, user_input: dict[str, Any] = None):
        """Handle a flow initialized by the user."""
        if user_input is not None:
            self._errors["base"] = None
            self._user_input.update(user_input)
            if user_input[CONNECTION_TYPE] == FOX_MODBUS_TCP:
                return await self.async_step_tcp()
            elif user_input[CONNECTION_TYPE] == FOX_MODBUS_SERIAL:
                return await self.async_step_serial()
            else:
                return await self.async_step_cloud()

        return self.async_show_form(
            step_id="inverter",
            data_schema=self._inverter_connection_schema,
            errors=self._errors,
        )

    async def async_step_tcp(self, user_input: dict[str, Any] = None):
        """Handle a flow initialized by the user."""
        if user_input is not None:
            self._errors["base"] = None
            modbus_valid = await self._test_fox_modbus(
                FOX_MODBUS_TCP,
                f"{user_input[FOX_MODBUS_HOST]}:{user_input[FOX_MODBUS_PORT]}",
                user_input[FOX_MODBUS_SLAVE],
            )
            if modbus_valid:
                self._errors["base"] = None
                self._user_input.update(user_input)
                return await self.async_step_battery()

        return self.async_show_form(
            step_id="tcp", data_schema=self._modbus_tcp_schema, errors=self._errors
        )

    async def async_step_serial(self, user_input: dict[str, Any] = None):
        """Handle a flow initialized by the user."""
        if user_input is not None:
            self._errors["base"] = None
            modbus_valid = await self._test_fox_modbus(
                FOX_MODBUS_SERIAL,
                user_input[FOX_MODBUS_HOST],
                user_input[FOX_MODBUS_SLAVE],
            )
            if modbus_valid:
                self._errors["base"] = None
                self._user_input.update(user_input)
                return await self.async_step_battery()

        return self.async_show_form(
            step_id="serial",
            data_schema=self._modbus_serial_schema,
            errors=self._errors,
        )

    async def async_step_cloud(self, user_input: dict[str, Any] = None):
        """Handle a flow initialized by the user."""
        if user_input is not None:
            fox_valid = await self._test_fox_cloud(user_input[FOX_API_KEY])
            if fox_valid:
                self._errors["base"] = None
                self._user_input.update(user_input)
                return await self.async_step_battery()
            else:
                self._errors["base"] = "fox_error"

        return self.async_show_form(
            step_id="cloud", data_schema=self._cloud_schema, errors=self._errors
        )

    async def async_step_battery(self, user_input: dict[str, Any] = None):
        """Handle a flow initialized by the user."""
        if user_input is not None:
            user_input[MIN_SOC] = round(user_input[MIN_SOC] / 100, 2)
            valid_times = self._parse_time(
                user_input[ECO_START_TIME], user_input[ECO_END_TIME]
            )
            if valid_times:
                self._errors["base"] = None
                self._user_input.update(user_input)
                return await self.async_step_power()
            else:
                self._errors["base"] = "time_invalid"

        schema = self._battery_schema
        if self._user_input[CONNECTION_TYPE] in [FOX_MODBUS_SERIAL, FOX_MODBUS_TCP]:
            schema = schema.extend(self._modbus_battery_schema)

        return self.async_show_form(
            step_id="battery", data_schema=schema, errors=self._errors
        )

    async def async_step_power(self, user_input: dict[str, Any] = None):
        """Handle a flow initialized by the user."""
        if user_input is not None:
            self._user_input.update(user_input)
            return self.async_create_entry(title=_TITLE, data=self._user_input)

        return self.async_show_form(step_id="power", data_schema=self._power_schema)

    def _parse_time(self, eco_start, eco_end):
        try:
            eco_start = datetime.time.fromisoformat(eco_start)
            eco_end = datetime.time.fromisoformat(eco_end)
            return True
        except ValueError:
            return False

    async def _test_solcast(self, solcast_api_key: str, solcast_url: str):
        """Return true if credentials is valid."""
        try:
            session = async_create_clientsession(self.hass)
            client = SolcastApiClient(solcast_api_key, solcast_url, session)
            result = await client.async_get_sites()
            if result is not None:
                return True
            else:
                return False
        except Exception as ex:  # pylint: disable=broad-except
            _LOGGER.warn(ex)
            pass
        return False

    async def _test_fox_cloud(self, fox_api_key: str):
        """Return true if API key is valid."""
        try:
            session = async_create_clientsession(self.hass)
            api = FoxCloudApiClient(session, fox_api_key)
            service = FoxCloudService(None, api, None, None)
            result = await service.device_info()
            if result is not None:
                return True
            else:
                return False
        except Exception as ex:  # pylint: disable=broad-except
            _LOGGER.warn(ex)
            pass
        return False

    async def _test_fox_modbus(self, conn_type, host, slave):
        """Return true if modbus connection can be established"""
        try:
            params = {CONNECTION_TYPE: conn_type}
            if conn_type == FOX_MODBUS_TCP:
                params.update({"host": host.split(":")[0], "port": host.split(":")[1]})
            else:
                params.update({"port": host, "baudrate": 9600})
            client = FoxModbus(self.hass, params)
            controller = FoxModbuservice(None, client, slave, None, None)
            return await controller.device_info()
        except ModbusException as ex:
            _LOGGER.warning(f"{ex!r}")
            self._errors["base"] = "modbus_error"
        return False

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry):
        """Get the options flow for this handler."""
        return BatteryManagerFlowHandler(config=config_entry)
