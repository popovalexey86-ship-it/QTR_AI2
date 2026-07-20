from abc import ABC, abstractmethod

from core.analysis_context import AnalysisContext
from core.market_data import MarketData


class Strategy(ABC):
    """Базовый интерфейс любой торговой стратегии."""

    @abstractmethod
    def analyze(
        self,
        market_data: MarketData,
    ) -> AnalysisContext:
        """
        Анализирует рынок и возвращает результат анализа.
        """
        raise NotImplementedError