from dataclasses import dataclass
from datetime import datetime

from core.bos_type import BOSType


@dataclass(slots=True, frozen=True)
class BOS:
    index: int
    timestamp: datetime
    price: float
    type: BOSType
