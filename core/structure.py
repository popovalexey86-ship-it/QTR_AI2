from dataclasses import dataclass
from datetime import datetime

from core.structure_type import StructureType


@dataclass(slots=True, frozen=True)
class Structure:
    """
    Структурный экстремум рынка.
    """

    index: int

    timestamp: datetime

    price: float

    type: StructureType
