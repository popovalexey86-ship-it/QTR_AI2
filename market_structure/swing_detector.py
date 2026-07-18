from core.market_data import MarketData
from core.swing import Swing
from core.swing_type import SwingType


class SwingDetector:
    """
    Поиск Swing High / Swing Low
    по классическому 5-свечному фракталу.
    """

    def __init__(self, window: int = 2):
        self.window = window

    def detect(self, market_data: MarketData) -> list[Swing]:

        swings: list[Swing] = []

        candles = market_data.candles

        for i in range(self.window, len(candles) - self.window):

            candle = candles[i]

            left = candles[i - self.window : i]
            right = candles[i + 1 : i + self.window + 1]

            # ---------- Swing HIGH ----------

            if all(candle.high > c.high for c in left) and all(
                candle.high > c.high for c in right
            ):

                swings.append(
                    Swing(
                        index=i,
                        timestamp=candle.timestamp,
                        price=candle.high,
                        type=SwingType.HIGH,
                    )
                )

            # ---------- Swing LOW ----------

            if all(candle.low < c.low for c in left) and all(
                candle.low < c.low for c in right
            ):

                swings.append(
                    Swing(
                        index=i,
                        timestamp=candle.timestamp,
                        price=candle.low,
                        type=SwingType.LOW,
                    )
                )

        return swings
