"""Custom sensor with optional properties"""

from dataclasses import dataclass

from homeassistant.components.number import NumberEntityDescription


@dataclass
class NumberDescription(NumberEntityDescription):
    """Custom number description"""

    set_method: str | None = None
    get_method: str | None = None
