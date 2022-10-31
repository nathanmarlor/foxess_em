"""Fox API Client."""
import asyncio
import hashlib
import logging

import aiohttp
import async_timeout

from ..util.exceptions import NoDataError

_TIMEOUT = 20
_LOGIN = "https://www.foxesscloud.com/c/v0/user/login"
_FOX_OK = 0
_FOX_INVALID_TOKEN = 41808
_FOX_TIMEOUT = 41203
_FOX_RETRIES = 5
_FOX_RETRY_DELAY = 10

_LOGGER: logging.Logger = logging.getLogger(__package__)


class FoxApiClient:
    """API client"""

    def __init__(
        self, session: aiohttp.ClientSession, fox_username: str, fox_password: str
    ) -> None:
        """Fox API Client."""
        self._session = session
        self._token = None
        self._fox_username = fox_username
        self._fox_password = hashlib.md5(str(fox_password).encode("utf-8")).hexdigest()
        self._fox_retries = 0

    async def _refresh_token(self) -> dict:
        """Refresh login token"""
        _LOGGER.debug("Logging into Fox Cloud")
        params = {"user": self._fox_username, "password": self._fox_password}
        result = await self._post_data(_LOGIN, params)
        self._token = {"token": result["token"]}

    async def async_post_data(self, url: str, params: dict[str, str]) -> dict:
        """Post data via the Fox API."""
        self._fox_retries = 0

        if self._token is None:
            await self._refresh_token()

        return await self._post_data(url, params)

    async def _post_data(self, url: str, params: dict[str, str]) -> dict:
        try:
            _LOGGER.debug(f"Issuing request to ({url}) with params: {params}")
            async with async_timeout.timeout(_TIMEOUT):
                response = await self._session.post(
                    url, json=params, headers=self._token
                )
        except Exception as ex:
            _LOGGER.error("Fox Cloud API error: %s", ex)

        if response.status == 200:
            result = await response.json(content_type=None)
            status = result["errno"]
            if status == _FOX_OK:
                return result["result"]
            elif status == _FOX_INVALID_TOKEN:
                _LOGGER.debug("Fox Cloud token has expired - refreshing...")
                await self._refresh_token()
                return await self._post_data(url, params)
            elif status == _FOX_TIMEOUT and self._fox_retries < _FOX_RETRIES:
                self._fox_retries += 1
                sleep_time = self._fox_retries * _FOX_RETRY_DELAY
                _LOGGER.debug(
                    f"Fox Cloud timeout - retrying {self._fox_retries}/{_FOX_RETRIES} after {sleep_time}s wait..."
                )
                await asyncio.sleep(sleep_time)
                return await self._post_data(url, params)
            else:
                raise NoDataError(
                    f"Could not make request to Fox Cloud - Error: {status}"
                )
        else:
            raise NoDataError(
                f"Could not make request to Fox Cloud - HTTP Status: {response.status}"
            )
