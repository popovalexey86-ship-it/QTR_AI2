from dataclasses import dataclass

from core.enums.setup_type import SetupType


@dataclass(slots=True, frozen=True)
class SetupAnalysis:
    """
    Результат поиска торгового сетапа.
    """

    found: bool

    setup: SetupType | None = None

    entry: float | None = None

    stop_loss: float | None = None

    take_profit: float | None = None