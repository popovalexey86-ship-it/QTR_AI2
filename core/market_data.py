from dataclasses import dataclass, field
from datetime import datetime, UTC

from core.candle import Candle


@dataclass(slots=True)
class MarketData:
    """
    Рыночные данные.

    Хранит информацию, необходимую для анализа рынка.
    Не выполняет никаких вычислений.
    """

    symbol: str

    timeframe: str

    candles: list[Candle] = field(default_factory=list)

    loaded_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def count(self) -> int:
        """Количество свечей."""
        return len(self.candles)

    @property
    def first(self) -> Candle:
        """Первая свеча."""
        return self.candles[0]

    @property
    def last(self) -> Candle:
        """Последняя свеча."""
        return self.candles[-1]

    def __len__(self) -> int:
        return len(self.candles)

    def __iter__(self):
        return iter(self.candles)

    def __getitem__(self, index):
        return self.candles[index]
