"""Custom sensor with optional properties"""

from dataclasses import dataclass, field

from homeassistant.components.sensor import SensorEntityDescription


@dataclass
class SensorDescription(SensorEntityDescription):
    """Custom sensor description"""

    should_poll: bool | None = False
    state_attributes: dict | None = field(default_factory=dict)
    visible: bool | None = True
    enabled: bool | None = True
    store_attributes: bool | None = False
    store_state: bool | None = False
