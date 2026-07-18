from core.market_structure import MarketStructure
from core.structure_point import StructurePoint
from core.structure_type import StructureType
from core.swing import Swing
from core.swing_type import SwingType

from services.structure_engine import StructureEngine


class PivotStructureEngine(StructureEngine):
    """
    Builds market structure from confirmed swings.
    """

    def build(self, swings: list[Swing]) -> MarketStructure:
        structure = MarketStructure()

        last_high: Swing | None = None
        last_low: Swing | None = None

        for swing in swings:

            if swing.type == SwingType.HIGH:
                if last_high is not None:
                    structure.points.append(
                        StructurePoint(
                            swing=swing,
                            type=(
                                StructureType.HH
                                if swing.price > last_high.price
                                else StructureType.LH
                            ),
                        )
                    )

                last_high = swing

            elif swing.type == SwingType.LOW:
                if last_low is not None:
                    structure.points.append(
                        StructurePoint(
                            swing=swing,
                            type=(
                                StructureType.HL
                                if swing.price > last_low.price
                                else StructureType.LL
                            ),
                        )
                    )

                last_low = swing

        return structure