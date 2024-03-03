"""Fox API Client."""

import asyncio
import hashlib
import logging
import time

import aiohttp
import async_timeout

from ..util.exceptions import NoDataError

_BASE_URL = "https://www.foxesscloud.com"
_TIMEOUT = 30
_FOX_OK = 0
_FOX_INVALID_TOKEN = 41808
_FOX_TIMEOUT = 41203
_FOX_RETRIES = 5
_FOX_RETRY_DELAY = 10

_LOGGER: logging.Logger = logging.getLogger(__package__)


class GetAuth:

    def get_signature(self, token, path, lang="en"):
        """
        This function is used to generate a signature consisting of URL, token, and timestamp, and
        return a dictionary containing the signature and other information.
            :param token: your key
            :param path:  your request path
            :param lang: language, default is English.
            :return: with authentication header
        """
        timestamp = round(time.time() * 1000)
        signature = rf"{path}\r\n{token}\r\n{timestamp}"
        # or use user_agent_rotator.get_random_user_agent() for user-agent
        result = {
            "token": token,
            "lang": lang,
            "timestamp": str(timestamp),
            "Content-Type": "application/json",
            "signature": self.md5c(text=signature),
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/117.0.0.0 Safari/537.36",
            "Connection": "close",
        }
        return result

    @staticmethod
    def md5c(text="", _type="lower"):
        res = hashlib.md5(text.encode(encoding="UTF-8")).hexdigest()
        if _type.__eq__("lower"):
            return res
        else:
            return res.upper()


class FoxCloudApiClient:
    """API client"""

    def __init__(self, session: aiohttp.ClientSession, fox_api_key: str) -> None:
        """Fox API Client."""
        self._session = session
        self._fox_api_key = fox_api_key
        self._fox_retries = 0

    async def async_post_data(self, path: str, params: dict[str, str]) -> dict:
        """Post data via the Fox API."""
        self._fox_retries = 0
        return await self._post_data(path, params)

    async def _post_data(self, path: str, params: dict[str, str]) -> dict:
        try:
            url = _BASE_URL + path
            header_data = GetAuth().get_signature(token=self._fox_api_key, path=path)

            _LOGGER.debug(f"Issuing request to ({url}) with params: {params}")
            async with async_timeout.timeout(_TIMEOUT):
                response = await self._session.post(
                    url, json=params, headers=header_data
                )
            # Leave 1 second between subsequent Fox calls
            await asyncio.sleep(1)
        except Exception as ex:
            raise NoDataError(f"Fox Cloud API error: {ex}")

        if response.status == 200:
            result = await response.json(content_type=None)
            status = result["errno"]
            if status == _FOX_OK:
                return result["result"]
            elif status == _FOX_INVALID_TOKEN:
                raise NoDataError(f"Fox Cloud API Key is not valid - Error: {status}")
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
