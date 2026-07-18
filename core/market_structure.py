from dataclasses import dataclass, field
from typing import Iterator

from core.structure_point import StructurePoint


@dataclass(slots=True)
class MarketStructure:
    """
    Represents the current market structure built from confirmed swings.
    """

    points: list[StructurePoint] = field(default_factory=list)

    def __len__(self) -> int:
        return len(self.points)

    def __iter__(self) -> Iterator[StructurePoint]:
        return iter(self.points)

    def __getitem__(self, index: int) -> StructurePoint:
        return self.points[index]

    @property
    def first(self) -> StructurePoint:
        return self.points[0]

    @property
    def last(self) -> StructurePoint:
        return self.points[-1]

    @property
    def is_empty(self) -> bool:
        return len(self.points) == 0
