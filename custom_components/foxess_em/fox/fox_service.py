"""Fox controller"""

import logging
from typing import Any

_LOGGER = logging.getLogger(__name__)


class FoxService:
    """Fox service"""

    async def start_force_charge_now(self, *_: Any) -> None:
        """Start force charge now"""
        pass

    async def start_force_charge_off_peak(self, *_: Any) -> None:
        """Start force charge off peak"""
        pass

    async def stop_force_charge(self, *_: Any) -> None:
        """Start force charge"""
        pass

    async def set_min_soc(
        self, soc: int, *_: Any
    ) -> None:
        """Set Min SoC"""
        pass

    async def set_charge_current(self, charge_current: float, *_: Any) -> None:
        """Set charge current"""
        pass

    async def device_info(self) -> None:
        """Get device info"""
        pass
