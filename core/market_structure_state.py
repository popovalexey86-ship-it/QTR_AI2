from dataclasses import dataclass

from core.bos import BOS
from core.choch import CHOCH
from core.structure import Structure
from core.trend import Trend


@dataclass(slots=True)
class MarketStructureState:

    trend: Trend = Trend.RANGE

    previous_hh: Structure | None = None
    last_hh: Structure | None = None

    previous_hl: Structure | None = None
    last_hl: Structure | None = None

    previous_lh: Structure | None = None
    last_lh: Structure | None = None

    previous_ll: Structure | None = None
    last_ll: Structure | None = None

    last_bos: BOS | None = None
    last_choch: CHOCH | None = None
