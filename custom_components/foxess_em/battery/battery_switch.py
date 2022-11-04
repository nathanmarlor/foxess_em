"""Battery switch"""
import logging

from ..common.switch import Switch
from ..common.switch_desc import SwitchDescription


_LOGGER = logging.getLogger(__name__)

_SWITCHES: dict[str, SwitchDescription] = {
    "boost": SwitchDescription(
        key="boost",
        name="Boost Charge (+1kW)",
        icon="mdi:rocket",
        is_on="boost_status",
        switch="set_boost",
    ),
    "full": SwitchDescription(
        key="full",
        name="Full Charge",
        icon="mdi:rocket",
        is_on="full_status",
        switch="set_full",
    ),
}


def switches(controllers, entry) -> list:
    """Setup sensor platform."""
    entities = []

    for switch in _SWITCHES:
        sen = Switch(controllers["battery"], entry, _SWITCHES[switch])
        entities.append(sen)

    return entities
