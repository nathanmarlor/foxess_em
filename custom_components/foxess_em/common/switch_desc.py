"""Custom sensor with optional properties"""
from dataclasses import dataclass

from custom_components.foxess_em.const import Connection
from homeassistant.components.switch import SwitchEntityDescription


@dataclass
class SwitchDescription(SwitchEntityDescription):
    """Custom switch description"""

    is_on: str | None = None
    switch: str | None = None
    store_state: bool | None = False
    connection: Connection | None = Connection.BOTH
