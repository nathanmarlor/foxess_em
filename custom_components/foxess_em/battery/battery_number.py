"""Battery switch"""
import logging

from custom_components.foxess_em.common.number import Number
from custom_components.foxess_em.common.number_desc import NumberDescription


_LOGGER = logging.getLogger(__name__)

_NUMBERS: dict[str, NumberDescription] = {
    "boost": NumberDescription(
        key="boost",
        name="Boost Charge",
        icon="mdi:rocket",
        set_method="set_boost",
        get_method="get_boost",
        native_min_value=0,
        native_max_value=5,
        native_step=0.5,
        native_unit_of_measurement="kWh",
    ),
}


def numbers(controllers, entry) -> list:
    """Setup sensor platform."""
    entities = []

    for number in _NUMBERS:
        sen = Number(controllers["battery"], entry, _NUMBERS[number])
        entities.append(sen)

    return entities
