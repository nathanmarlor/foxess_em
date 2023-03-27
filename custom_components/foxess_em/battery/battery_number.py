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
        set="set_boost",
        get="get_boost",
    ),
}


def numbers(controllers, entry) -> list:
    """Setup sensor platform."""
    entities = []

    for number in _NUMBERS:
        sen = Number(controllers["battery"], entry, _NUMBERS[number])
        entities.append(sen)

    return entities
