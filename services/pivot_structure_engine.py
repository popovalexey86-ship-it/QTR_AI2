from core.structure_point import StructurePoint
from core.structure_type import StructureType
from core.swing import Swing
from core.swing_type import SwingType

from services.structure_engine import StructureEngine


class PivotStructureEngine(StructureEngine):
    """
    Builds market structure from confirmed swings.
    """

    def build(self, swings: list[Swing]) -> list[StructurePoint]:
        structure: list[StructurePoint] = []

        if len(swings) < 2:
            return structure

        previous = swings[0]

        for current in swings[1:]:
            if current.type != previous.type:
                previous = current
                continue

            if current.type == SwingType.HIGH:
                structure_type = (
                    StructureType.HH
                    if current.price > previous.price
                    else StructureType.LH
                )
            else:
                structure_type = (
                    StructureType.HL
                    if current.price > previous.price
                    else StructureType.LL
                )

            structure.append(
                StructurePoint(
                    swing=current,
                    type=structure_type,
                )
            )

            previous = current

        return structure