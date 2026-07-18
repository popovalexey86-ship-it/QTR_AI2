from dataclasses import dataclass
from datetime import datetime

from core.choch_type import CHOCHType


@dataclass(slots=True, frozen=True)
class CHOCH:
    index: int
    timestamp: datetime
    price: float
    type: CHOCHType
