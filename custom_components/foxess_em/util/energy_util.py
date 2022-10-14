"""Energy utilities"""
from datetime import timedelta

import pandas as pd


def resample(values):
    """Resample dict of datetime/value to 1m"""
    df = pd.DataFrame.from_dict(values)
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df["datetime"] = pd.to_datetime(df["datetime"], utc=True)

    df = df.dropna()
    full_data = df.set_index("datetime").resample("1T").mean().interpolate("linear")

    full_data["datetime"] = full_data.index.values

    return full_data


def sum_energy(values):
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
