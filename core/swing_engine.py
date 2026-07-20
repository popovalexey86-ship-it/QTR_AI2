from core.market_data import MarketData
from core.swing import Swing

from services.pivot_swing_detector import PivotSwingDetector


class SwingEngine:

    def __init__(self):
        self._detector = PivotSwingDetector()

    def detect(self, market_data: MarketData) -> list[Swing]:
        return self._detector.detect(market_data)