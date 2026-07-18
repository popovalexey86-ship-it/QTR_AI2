from enum import Enum


class StructureType(Enum):
    """
    Тип структурного экстремума.
    """

    HH = "HH"  # Higher High

    HL = "HL"  # Higher Low

    LH = "LH"  # Lower High

    LL = "LL"  # Lower Low
