"""Battery controller"""
import logging

_LOGGER = logging.getLogger(__name__)
_MAX_PERC = 100


class BatteryUtils:
    """Battery Utils"""

    def __init__(self, capacity: float, min_soc: float) -> None:
        """Init"""
        self._capacity = capacity
        self._min_soc = min_soc

    def charge_to_perc(self, charge: float) -> float:
        """Convert kWh to percentage of charge"""
        perc = ((charge / self._capacity) + self._min_soc) * 100

        return min(_MAX_PERC, round(perc, 0))

    def ceiling_charge_total(self, charge_total: float) -> float:
        """Ceiling total charge"""
        available_capacity = round(
            self._capacity - (self._min_soc * self._capacity),
            2,
        )

        return round(min(available_capacity, charge_total), 2)
