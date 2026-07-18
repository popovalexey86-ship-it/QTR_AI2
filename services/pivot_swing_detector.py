from core.market_data import MarketData
from core.swing import Swing
from core.swing_type import SwingType
from services.swing_detector import SwingDetector


class PivotSwingDetector(SwingDetector):
    """
    Detects confirmed Pivot Left/Right (2x2) swings.
    """

    LEFT = 2
    RIGHT = 2

    def detect(self, market_data: MarketData) -> list[Swing]:
        swings: list[Swing] = []
        candles = market_data.candles

        if len(candles) < self.LEFT + self.RIGHT + 1:
            return swings

        for i in range(self.LEFT, len(candles) - self.RIGHT):
            candle = candles[i]

            is_swing_high = (
                candle.high > candles[i - 1].high
                and candle.high > candles[i - 2].high
                and candle.high > candles[i + 1].high
                and candle.high > candles[i + 2].high
            )

            if is_swing_high:
                swings.append(
                    Swing(
                        index=i,
                        timestamp=candle.timestamp,
                        price=candle.high,
                        type=SwingType.HIGH,
                    )
                )

            is_swing_low = (
                candle.low < candles[i - 1].low
                and candle.low < candles[i - 2].low
                and candle.low < candles[i + 1].low
                and candle.low < candles[i + 2].low
            )

            if is_swing_low:
                swings.append(
                    Swing(
                        index=i,
                        timestamp=candle.timestamp,
                        price=candle.low,
                        type=SwingType.LOW,
                    )
                )

        return swings