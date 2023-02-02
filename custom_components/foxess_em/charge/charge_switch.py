"""Battery switch"""
import logging

from ..common.switch import Switch
from ..common.switch_desc import SwitchDescription


_LOGGER = logging.getLogger(__name__)

_SWITCHES: dict[str, SwitchDescription] = {
    "disable": SwitchDescription(
        key="disable",
        name="Disable Auto Charge",
        icon="mdi:sync-off",
        is_on="disable_status",
        switch="set_disable",
        store_state=True,
    ),
    "custom_charge_profile": SwitchDescription(
        key="custom_charge_profile",
        name="Custom Charge Profile",
        icon="mdi:chart-line",
        is_on="custom_charge_profile_status",
        switch="set_custom_charge_profile",
        store_state=True,
    ),
}


def switches(controllers, entry) -> list:
    """Setup sensor platform."""
    entities = []

    for switch in _SWITCHES:
        sen = Switch(controllers["charge"], entry, _SWITCHES[switch])
        entities.append(sen)

    return entities
