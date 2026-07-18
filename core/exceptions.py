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
