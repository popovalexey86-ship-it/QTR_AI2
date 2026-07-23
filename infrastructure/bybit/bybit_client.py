from collections.abc import Callable
import time
from typing import TypeVar

import requests
from pybit.exceptions import FailedRequestError, InvalidRequestError
from pybit.unified_trading import HTTP

from core.exceptions import (
    BrokerError,
    RateLimitError,
    TemporaryExchangeError,
    TemporaryTransportError,
    UnknownWriteOutcomeError,
)
from core.logger import logger
from infrastructure.config import Config


T = TypeVar("T")
_READ_RETRY_DELAYS = (0.5, 1.5)
_TEMPORARY_BYBIT_CODES = frozenset({10000, 10016})
_RATE_LIMIT_CODES = frozenset({429, 10006})


class BybitClient:

    def __init__(
        self,
        config: Config,
        sleep_fn: Callable[[float], None] = time.sleep,
    ):
        self._is_testnet = config.bybit_testnet
        self._sleep = sleep_fn
        self._session = HTTP(
            testnet=self._is_testnet,
            api_key=config.bybit_api_key,
            api_secret=config.bybit_api_secret,
        )

    @property
    def is_testnet(self) -> bool:
        return self._is_testnet

    def get_server_time(self) -> dict:
        return self._session.get_server_time()

    def get_klines(
        self,
        category: str,
        symbol: str,
        interval: str,
        limit: int,
    ) -> dict:
        return self._read_request(
            "get_klines",
            lambda: self._session.get_kline(
                category=category,
                symbol=symbol,
                interval=interval,
                limit=limit,
            ),
        )

    def place_order(
        self,
        **kwargs,
    ) -> dict:
        return self._write_request(
            "place_order",
            lambda: self._session.place_order(**kwargs),
        )

    def get_positions(
        self,
        category: str,
        symbol: str,
    ) -> dict:
        return self._read_request(
            "get_positions",
            lambda: self._session.get_positions(
                category=category,
                symbol=symbol,
            ),
        )

    def get_closed_pnl(
        self,
        category: str,
        symbol: str,
        limit: int = 1,
    ) -> dict:
        return self._read_request(
            "get_closed_pnl",
            lambda: self._session.get_closed_pnl(
                category=category,
                symbol=symbol,
                limit=limit,
            ),
        )

    def get_open_orders(
        self,
        category: str,
        symbol: str,
        order_link_id: str,
    ) -> dict:
        return self._read_request(
            "get_open_orders",
            lambda: self._session.get_open_orders(
                category=category,
                symbol=symbol,
                orderLinkId=order_link_id,
            ),
        )

    def list_open_orders(
        self,
        category: str,
        symbol: str,
    ) -> dict:
        return self._read_request(
            "list_open_orders",
            lambda: self._session.get_open_orders(
                category=category,
                symbol=symbol,
            ),
        )

    def get_order_history(
        self,
        category: str,
        symbol: str,
        order_link_id: str,
    ) -> dict:
        return self._read_request(
            "get_order_history",
            lambda: self._session.get_order_history(
                category=category,
                symbol=symbol,
                orderLinkId=order_link_id,
            ),
        )

    def cancel_order(
        self,
        category: str,
        symbol: str,
        order_link_id: str,
        order_id: str | None = None,
    ) -> dict:
        parameters = {
            "category": category,
            "symbol": symbol,
            "orderLinkId": order_link_id,
        }
        if order_id is not None:
            parameters["orderId"] = order_id
        return self._write_request(
            "cancel_order",
            lambda: self._session.cancel_order(**parameters),
        )

    def _write_request(
        self,
        operation: str,
        request: Callable[[], T],
    ) -> T:
        try:
            return request()
        except (
            requests.ReadTimeout,
            requests.ConnectionError,
            requests.exceptions.SSLError,
            requests.HTTPError,
            FailedRequestError,
            InvalidRequestError,
        ) as error:
            if _classify_read_error(operation, error) is not None:
                raise UnknownWriteOutcomeError(
                    "Bybit write outcome is unknown. "
                    f"Operation={operation}."
                ) from None
            raise

    def _read_request(
        self,
        operation: str,
        request: Callable[[], T],
    ) -> T:
        for attempt in range(1, len(_READ_RETRY_DELAYS) + 2):
            try:
                response = request()
                response_error = _classify_response(operation, response)
                if response_error is not None:
                    raise response_error
                return response
            except (
                requests.ReadTimeout,
                requests.ConnectionError,
                requests.exceptions.SSLError,
                requests.HTTPError,
                FailedRequestError,
                InvalidRequestError,
                BrokerError,
            ) as error:
                classified = _classify_read_error(operation, error)
                if classified is None:
                    raise _safe_permanent_error(operation, error) from None
                if attempt > len(_READ_RETRY_DELAYS):
                    raise classified from None

                logger.warning(
                    "Bybit read retry. Operation=%s Attempt=%s ErrorType=%s",
                    operation,
                    attempt,
                    type(error).__name__,
                )
                self._sleep(_READ_RETRY_DELAYS[attempt - 1])

        raise AssertionError("Unreachable Bybit read retry state.")


def _classify_response(
    operation: str,
    response: object,
) -> BrokerError | None:
    if not isinstance(response, dict):
        return None
    code = response.get("retCode")
    if code in _RATE_LIMIT_CODES:
        return RateLimitError(
            f"Bybit rate limit exceeded. Operation={operation}."
        )
    if code in _TEMPORARY_BYBIT_CODES:
        return TemporaryExchangeError(
            f"Bybit is temporarily unavailable. Operation={operation}."
        )
    if code not in (None, 0):
        return BrokerError(f"Bybit request failed. Operation={operation}.")
    return None


def _classify_read_error(
    operation: str,
    error: Exception,
) -> BrokerError | None:
    if isinstance(
        error,
        (
            requests.ReadTimeout,
            requests.ConnectionError,
            requests.exceptions.SSLError,
        ),
    ):
        return TemporaryTransportError(
            f"Bybit transport is temporarily unavailable. Operation={operation}."
        )
    if isinstance(error, RateLimitError):
        return error
    if isinstance(error, TemporaryExchangeError):
        return error
    if isinstance(error, (FailedRequestError, InvalidRequestError)):
        status_code = error.status_code
        if status_code in _RATE_LIMIT_CODES:
            return RateLimitError(
                f"Bybit rate limit exceeded. Operation={operation}."
            )
        if status_code in _TEMPORARY_BYBIT_CODES or (
            isinstance(status_code, int) and 500 <= status_code <= 599
        ):
            return TemporaryExchangeError(
                f"Bybit is temporarily unavailable. Operation={operation}."
            )
    if isinstance(error, requests.HTTPError):
        status_code = (
            None if error.response is None else error.response.status_code
        )
        if status_code == 429:
            return RateLimitError(
                f"Bybit rate limit exceeded. Operation={operation}."
            )
        if status_code is not None and 500 <= status_code <= 599:
            return TemporaryExchangeError(
                f"Bybit is temporarily unavailable. Operation={operation}."
            )
    return None


def _safe_permanent_error(operation: str, error: Exception) -> BrokerError:
    if isinstance(error, BrokerError):
        return error
    return BrokerError(
        "Bybit read request failed without retry. "
        f"Operation={operation} ErrorType={type(error).__name__}."
    )
