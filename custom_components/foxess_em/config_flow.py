"""Adds config flow for foxess_em."""
import datetime
import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from ..foxess_em.const import DAWN_BUFFER
from ..foxess_em.const import DAY_BUFFER
from ..foxess_em.const import MIN_SOC
from .const import AUX_POWER
from .const import BATTERY_CAPACITY
from .const import BATTERY_SOC
from .const import CHARGE_RATE
from .const import DOMAIN
from .const import ECO_END_TIME
from .const import ECO_START_TIME
from .const import FOX_PASSWORD
from .const import FOX_USERNAME
from .const import HOUSE_POWER
from .const import SOLCAST_API_KEY
from .const import SOLCAST_URL
from .forecast.solcast_api import SolcastApiClient
from .fox.fox_api import FoxApiClient
from .fox.fox_cloud_service import FoxCloudService

_TITLE = "FoxESS - Energy Management"

_LOGGER = logging.getLogger(__name__)


class BatteryManagerFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for foxess_em."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

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
                ): str,
            }
        )

        self._fox_schema = vol.Schema(
            {
                vol.Required(
                    FOX_USERNAME,
                    default=self._data.get(FOX_USERNAME, ""),
                ): str,
                vol.Required(
                    FOX_PASSWORD,
                    default=self._data.get(FOX_PASSWORD, ""),
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
                ): vol.All(vol.Coerce(float), vol.Range(min=0, max=5)),
                vol.Required(
                    DAY_BUFFER, default=self._data.get(DAY_BUFFER, 2)
                ): vol.All(vol.Coerce(float), vol.Range(min=0, max=5)),
                vol.Required(
                    BATTERY_CAPACITY, default=self._data.get(BATTERY_CAPACITY, 10.4)
                ): vol.Coerce(float),
                vol.Required(
                    MIN_SOC,
                    default=self._data.get(MIN_SOC, 0.11) * 100,
                ): vol.All(vol.Coerce(float), vol.Range(min=10, max=99)),
                vol.Required(
                    CHARGE_RATE,
                    default=self._data.get(CHARGE_RATE, 18),
                ): vol.All(vol.Coerce(float), vol.Range(min=1, max=99)),
            }
        )

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
                return await self.async_step_fox()
            else:
                self._errors["base"] = "solcast_auth"

        return self.async_show_form(
            step_id="user", data_schema=self._solcast_schema, errors=self._errors
        )

    async def async_step_fox(self, user_input: dict[str, Any] = None):
        """Handle a flow initialized by the user."""
        if user_input is not None:
            fox_valid = await self._test_fox(
                user_input[FOX_USERNAME], user_input[FOX_PASSWORD]
            )
            if fox_valid:
                self._errors["base"] = None
                self._user_input.update(user_input)
                return await self.async_step_battery()
            else:
                self._errors["base"] = "fox_auth"

        return self.async_show_form(
            step_id="fox", data_schema=self._fox_schema, errors=self._errors
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

        return self.async_show_form(
            step_id="battery", data_schema=self._battery_schema, errors=self._errors
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

    async def _test_fox(self, fox_username: str, fox_password: str):
        """Return true if credentials is valid."""
        try:
            session = async_create_clientsession(self.hass)
            api = FoxApiClient(session, fox_username, fox_password)
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

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry):
        """Get the options flow for this handler."""
        return BatteryManagerFlowHandler(config=config_entry)
