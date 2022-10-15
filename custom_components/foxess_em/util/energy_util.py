"""Energy utilities"""
from datetime import timedelta


def sum_energy(values: list[dict]):
    """Sum power values into energy"""

    energy_total = 0
    for i in range(len(values) - 1):
        energy_period = values[i]["value"]

        time_period = values[i]["datetime"]
        next_time_period = values[i + 1]["datetime"]

        time_delta = next_time_period - time_period

        # Missing data - reset energy period to 0
        if time_delta > timedelta(hours=1):
            energy_period = 0

        energy_total += (energy_period * time_delta.total_seconds()) / 3600

    return energy_total
