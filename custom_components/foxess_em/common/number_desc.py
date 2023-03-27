"""Custom sensor with optional properties"""
from dataclasses import dataclass

from homeassistant.components.number import NumberEntityDescription


@dataclass
class NumberDescription(NumberEntityDescription):
    """Custom number description"""

    set: str | None = None
    get: str | None = None
    min: float | None = 0
    max: float | None = 0
    step: float | None = 0.5
