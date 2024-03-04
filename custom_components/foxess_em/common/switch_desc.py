"""Custom sensor with optional properties"""

from dataclasses import dataclass

from homeassistant.components.switch import SwitchEntityDescription

from custom_components.foxess_em.const import Connection


@dataclass
class SwitchDescription(SwitchEntityDescription):
    """Custom switch description"""

    is_on: str | None = None
    switch: str | None = None
    store_state: bool | None = False
    connection: Connection | None = Connection.BOTH
