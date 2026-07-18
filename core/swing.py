from dataclasses import dataclass
from datetime import datetime

from core.swing_type import SwingType


@dataclass(slots=True, frozen=True)
class Swing:
    """
    Подтвержденный локальный экстремум.
    """

    index: int

    timestamp: datetime

    price: float

    type: SwingType