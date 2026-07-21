class BrokerError(Exception):
    """
    Базовое исключение брокера.
    """

    pass


class OrderRejectedError(BrokerError):
    """
    Биржа отклонила заявку.
    """

    pass


class PositionNotFoundError(BrokerError):
    """
    Позиция не найдена.
    """

    pass


class DuplicatePendingSetupError(Exception):
    """Raised when an already submitted structural setup is suppressed."""


class PendingEntryConflictError(Exception):
    """Raised when a position or pending entry blocks a new submission."""


class PendingEntrySubmissionError(Exception):
    """Raised when a broker acknowledgement has no pending-entry state."""
