from dataclasses import dataclass

from core.structure_type import StructureType
from core.swing import Swing


@dataclass(slots=True, frozen=True)
class StructurePoint:
    swing: Swing
    type: StructureType
