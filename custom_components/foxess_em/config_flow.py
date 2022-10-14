"""Adds config flow for foxess_em."""
import datetime
import logging

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from ..foxess_em.const import DAWN_BUFFER
from ..foxess_em.const import DAY_BUFFER
from ..foxess_em.const import MIN_SOC
from .const import AUX_POWER
from .const import BATTERY_CAPACITY
from .const import CHARGE_RATE
from .const import DOMAIN
from .const import ECO_END_TIME
from .const import ECO_START_TIME
from .const import FOX_PASSWORD
from .const import FOX_USERNAME
from .const import HOUSE_POWER
from .const import SOLCAST_API_KEY
from .const import SOLCAST_API_SITE
from .const import SOLCAST_URL
from .forecast.solcast_api import SolcastApiClient
from .fox.fox_api import FoxApiClient
from .fox.fox_cloud_service import FoxCloudService

_TITLE = "FoxESS - Energy Management"

_LOGGER = logging.getLogger(__name__)

_SOLCAST_SCHEMA = vol.Schema(
    {
        vol.Required(SOLCAST_API_SITE): str,
        vol.Required(SOLCAST_API_KEY): str,
    }
)

_FOX_SCHEMA = vol.Schema(
    {
        vol.Required(FOX_USERNAME): str,
        vol.Required(FOX_PASSWORD): str,
    }
)

_BATTERY_SCHEMA = vol.Schema(
    {
        vol.Required(ECO_START_TIME, default=datetime.time(0, 30).isoformat()): str,
        vol.Required(ECO_END_TIME, default=datetime.time(4, 30).isoformat()): str,
        vol.Required(DAWN_BUFFER, default=1): vol.All(
            vol.Coerce(float), vol.Range(min=0, max=5)
        ),
        vol.Required(DAY_BUFFER, default=2): vol.All(
            vol.Coerce(float), vol.Range(min=0, max=5)
        ),
        vol.Required(BATTERY_CAPACITY, default=10.4): vol.Coerce(float),
        vol.Required(CHARGE_RATE, default=3.4): vol.All(
            vol.Coerce(float), vol.Range(min=3, max=10)
        ),
        vol.Required(MIN_SOC, default=10): vol.All(
            vol.Coerce(float), vol.Range(min=10, max=99)
        ),
    }
)

_POWER_SCHEMA = vol.Schema(
    {
        vol.Required(HOUSE_POWER, default="sensor.load_power"): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="sensor", multiple=False)
        ),
        vol.Required(AUX_POWER): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="sensor", multiple=True)
        ),
    }
)


class BatteryManagerFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for foxess_em."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self):
        """Initialize."""
        self._errors = {}
        self._data = None

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        self._errors = {}

        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        if user_input is not None:
            solcast_valid = await self._test_solcast(
                user_input[SOLCAST_API_SITE], user_input[SOLCAST_API_KEY], SOLCAST_URL
            )
            if solcast_valid:
                self._errors["base"] = None
                self._data = user_input
                return await self.async_step_fox()
            else:
                self._errors["base"] = "solcast_auth"

        return self.async_show_form(
            step_id="user", data_schema=_SOLCAST_SCHEMA, errors=self._errors
        )

    async def async_step_fox(self, user_input=None):
        """Handle a flow initialized by the user."""
        if user_input is not None:
            fox_valid = await self._test_fox(
                user_input[FOX_USERNAME], user_input[FOX_PASSWORD]
            )
            if fox_valid:
                self._errors["base"] = None
                self._data.update(user_input)
                return await self.async_step_battery()
            else:
                self._errors["base"] = "fox_auth"

        return self.async_show_form(
            step_id="fox", data_schema=_FOX_SCHEMA, errors=self._errors
        )

    async def async_step_battery(self, user_input=None):
        """Handle a flow initialized by the user."""
        if user_input is not None:
            user_input[MIN_SOC] = round(user_input[MIN_SOC] / 100, 2)
            valid_times = self._parse_time(
                user_input[ECO_START_TIME], user_input[ECO_END_TIME]
            )
            if valid_times:
                self._errors["base"] = None
                self._data.update(user_input)
                return await self.async_step_power()
            else:
                self._errors["base"] = "time_invalid"

        return self.async_show_form(
            step_id="battery", data_schema=_BATTERY_SCHEMA, errors=self._errors
        )

    async def async_step_power(self, user_input=None):
        """Handle a flow initialized by the user."""
        if user_input is not None:
            self._data.update(user_input)
            return self.async_create_entry(title=_TITLE, data=self._data)

        return self.async_show_form(step_id="power", data_schema=_POWER_SCHEMA)

    def _parse_time(self, eco_start, eco_end):
        try:
            eco_start = datetime.time.fromisoformat(eco_start)
            eco_end = datetime.time.fromisoformat(eco_end)
            return True
        except ValueError:
            return False

    async def _test_solcast(self, solcast_site_id, solcast_api_key, solcast_url):
        """Return true if credentials is valid."""
        try:
            session = async_create_clientsession(self.hass)
            client = SolcastApiClient(
                solcast_site_id, solcast_api_key, solcast_url, session
            )
            result = await client.async_get_data()
            if result is not None:
                return True
            else:
                return False
        except Exception as ex:  # pylint: disable=broad-except
            _LOGGER.warn(ex)
            pass
        return False

    async def _test_fox(self, fox_username, fox_password):
        """Return true if credentials is valid."""
        try:
            session = async_create_clientsession(self.hass)
            api = FoxApiClient(session, fox_username, fox_password)
            service = FoxCloudService(api)
            result = await service.device_serial_number()
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
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handles options flow for the component."""

    def __init__(self, config: config_entries.ConfigEntry) -> None:
        self._config = config
        self.options = dict(config.options)
        self._schema = vol.Schema(
            {
                vol.Required(
                    DAWN_BUFFER,
                    default=self._config.options.get(
                        DAWN_BUFFER, self._config.data.get(DAWN_BUFFER)
                    ),
                ): vol.All(vol.Coerce(float), vol.Range(min=0, max=5)),
                vol.Required(
                    DAY_BUFFER,
                    default=self._config.options.get(
                        DAY_BUFFER, self._config.data.get(DAY_BUFFER)
                    ),
                ): vol.All(vol.Coerce(float), vol.Range(min=0, max=5)),
                vol.Required(
                    BATTERY_CAPACITY,
                    default=self._config.options.get(
                        BATTERY_CAPACITY, self._config.data.get(BATTERY_CAPACITY)
                    ),
                ): vol.Coerce(float),
                vol.Required(
                    CHARGE_RATE,
                    default=self._config.options.get(
                        CHARGE_RATE, self._config.data.get(CHARGE_RATE)
                    ),
                ): vol.All(vol.Coerce(float), vol.Range(min=3, max=10)),
                vol.Required(
                    MIN_SOC,
                    default=self._config.options.get(
                        MIN_SOC, self._config.data.get(MIN_SOC)
                    )
                    * 100,
                ): vol.All(vol.Coerce(float), vol.Range(min=10, max=99)),
                vol.Required(
                    AUX_POWER,
                    default=self._config.options.get(
                        AUX_POWER, self._config.data.get(AUX_POWER)
                    ),
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor", multiple=True)
                ),
            }
        )

    async def async_step_init(self, user_input):
        """Manage the options for the custom component."""
        if user_input is not None:
            user_input[MIN_SOC] = round(user_input[MIN_SOC] / 100, 2)
            self.options.update(user_input)
            return self.async_create_entry(title=_TITLE, data=self.options)

        return self.async_show_form(step_id="init", data_schema=self._schema)
