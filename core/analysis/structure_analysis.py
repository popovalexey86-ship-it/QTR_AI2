from dataclasses import dataclass

from core.enums.market_structure import MarketStructure


@dataclass(slots=True, frozen=True)
class StructureAnalysis:
    """
    Результат анализа структуры рынка.
    """

    structure: MarketStructure

    bos: bool

    choch: bool