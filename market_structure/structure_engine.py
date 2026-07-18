from core.structure import Structure
from core.structure_type import StructureType
from core.swing import Swing
from core.swing_type import SwingType


class StructureEngine:
    """
    Преобразует Swing в Structure.
    """

    def detect(self, swings: list[Swing]) -> list[Structure]:

        structures: list[Structure] = []

        last_high: Swing | None = None
        last_low: Swing | None = None

        for swing in swings:

            if swing.type == SwingType.HIGH:

                if last_high is not None:

                    structure_type = (
                        StructureType.HH
                        if swing.price > last_high.price
                        else StructureType.LH
                    )

                    structures.append(
                        Structure(
                            index=swing.index,
                            timestamp=swing.timestamp,
                            price=swing.price,
                            type=structure_type,
                        )
                    )

                last_high = swing

            elif swing.type == SwingType.LOW:

                if last_low is not None:

                    structure_type = (
                        StructureType.HL
                        if swing.price > last_low.price
                        else StructureType.LL
                    )

                    structures.append(
                        Structure(
                            index=swing.index,
                            timestamp=swing.timestamp,
                            price=swing.price,
                            type=structure_type,
                        )
                    )

                last_low = swing

        return structures