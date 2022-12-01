"""Callback controller"""
import asyncio
import logging
from typing import Callable

from homeassistant.core import CoreState
from homeassistant.core import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


class HassLoadController:
    """Hass Load controller base"""

    def __init__(self, hass: HomeAssistant, func: Callable) -> None:
        """Init"""

        if hass.state is CoreState.running:
            asyncio.run_coroutine_threadsafe(func(), hass.loop)
        else:
            hass.bus.async_listen_once(
                EVENT_HOMEASSISTANT_STARTED,
                func,
            )
