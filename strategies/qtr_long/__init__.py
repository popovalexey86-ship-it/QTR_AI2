"""QTR Long strategy package.

QTR Long is a buy-only strategy family. Bearish information may block a long
entry, but it must never be converted into a short entry.
"""

from strategies.qtr_long.decision_engine import LongDecisionEngine
from strategies.qtr_long.regime import LongMarketRegime, LongRegimeEngine
from strategies.qtr_long.score import LongScore, LongScoreGrade
from strategies.qtr_long.scoring import LongScoringEngine
from strategies.qtr_long.setup import LongSetupCandidate, LongSetupType
from strategies.qtr_long.setup_detector import LongSetupDetector
from strategies.qtr_long.strategy import QTRLongStrategy

__all__ = [
    "LongDecisionEngine",
    "LongMarketRegime",
    "LongRegimeEngine",
    "LongScore",
    "LongScoreGrade",
    "LongScoringEngine",
    "LongSetupCandidate",
    "LongSetupDetector",
    "LongSetupType",
    "QTRLongStrategy",
]
