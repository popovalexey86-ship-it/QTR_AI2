from abc import ABC, abstractmethod

from core.structure_point import StructurePoint
from core.swing import Swing


class StructureEngine(ABC):
    """
    Builds market structure from confirmed swings.
    """

    @abstractmethod
    def build(self, swings: list[Swing]) -> list[StructurePoint]:
        raise NotImplementedError