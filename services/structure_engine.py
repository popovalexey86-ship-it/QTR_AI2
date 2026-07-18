from abc import ABC, abstractmethod

from core.market_structure import MarketStructure
from core.swing import Swing


class StructureEngine(ABC):
    """
    Interface for building market structure from confirmed swings.
    """

    @abstractmethod
    def build(self, swings: list[Swing]) -> MarketStructure:
        """
        Build market structure from a sequence of confirmed swings.
        """
        raise NotImplementedError