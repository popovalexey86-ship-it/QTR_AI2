from abc import ABC, abstractmethod

from core.market_data import MarketData
from core.swing import Swing


class SwingDetector(ABC):
    """
    Interface for swing detection algorithms.
    """

    @abstractmethod
    def detect(self, market_data: MarketData) -> list[Swing]:
        """
        Detect confirmed swings in market data.
        """
        raise NotImplementedError