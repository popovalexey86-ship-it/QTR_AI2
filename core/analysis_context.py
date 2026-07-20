from dataclasses import dataclass, field

from core.market_data import MarketData
from core.swing import Swing
from core.structure import Structure
from core.market_structure_state import MarketStructureState
from core.bos import BOS
from core.choch import CHOCH
from core.trend import Trend
from core.setup import Setup


@dataclass
class AnalysisContext:
    """
    Контейнер результатов полного анализа рынка.
    """

    # Исходные данные
    market_data: MarketData

    # Этап 1
    swings: list[Swing] = field(default_factory=list)

    # Этап 2
    structures: list[Structure] = field(default_factory=list)

    # Этап 3
    market_structure_state: MarketStructureState | None = None

    # Этап 4
    bos: BOS | None = None

    # Этап 5
    choch: CHOCH | None = None

    # Этап 6
    trend: Trend | None = None

    # Этап 7
    setup: Setup | None = None