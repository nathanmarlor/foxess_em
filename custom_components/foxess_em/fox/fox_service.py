"""Fox controller"""

import logging

_LOGGER = logging.getLogger(__name__)


class FoxService:
    """Fox service"""

    async def start_force_charge_now(self, *args) -> None:
        """Start force charge now"""
        pass

    async def start_force_charge_off_peak(self, *args) -> None:
        """Start force charge off peak"""
        pass

    async def stop_force_charge(self, *args) -> None:  # pylint: disable=unused-argument
        """Start force charge"""
        pass

    async def set_min_soc(
        self, soc: int, *args
    ) -> None:  # pylint: disable=unused-argument
        """Set Min SoC"""
        pass

    async def set_charge_current(self, charge_current: float, *args) -> None:
        """Set charge current"""
        pass

    async def device_info(self) -> None:
        """Get device info"""
        pass
