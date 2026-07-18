from core.bos import BOS
from core.bos_type import BOSType
from core.structure import Structure
from core.structure_type import StructureType


class BOSEngine:
    """
    Определяет Break Of Structure (BOS)
    по последовательности Structure.
    """

    def detect(self, structures: list[Structure]) -> list[BOS]:

        bos_list: list[BOS] = []

        for i in range(1, len(structures)):

            previous = structures[i - 1]
            current = structures[i]

            # Bullish BOS
            if previous.type == StructureType.HH and current.type == StructureType.HH:
                bos_list.append(
                    BOS(
                        index=current.index,
                        timestamp=current.timestamp,
                        price=current.price,
                        type=BOSType.BULLISH,
                    )
                )

            # Bearish BOS
            elif previous.type == StructureType.LL and current.type == StructureType.LL:
                bos_list.append(
                    BOS(
                        index=current.index,
                        timestamp=current.timestamp,
                        price=current.price,
                        type=BOSType.BEARISH,
                    )
                )

        return bos_list
