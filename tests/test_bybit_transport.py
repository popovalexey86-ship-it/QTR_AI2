from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import Mock, call

import pytest
import requests
from pybit.exceptions import FailedRequestError, InvalidRequestError

from core.decision import Decision
from core.exceptions import (
    BrokerError,
    RateLimitError,
    TemporaryExchangeError,
    TemporaryTransportError,
)
from core.setup import Setup
from core.trade_request import TradeRequest
from core.trend import Trend
import infrastructure.bybit.bybit_client as bybit_client_module
from infrastructure.bybit.bybit_broker import BybitBroker
from infrastructure.bybit.bybit_client import BybitClient
from infrastructure.bybit.bybit_pending_entry_store import BybitPendingEntryStore
from infrastructure.config import Config


ORDER_LINK_ID = "QTR-0123456789abcdef"
SIGNAL_TIMESTAMP = datetime(2026, 1, 2, 3, 4, tzinfo=UTC)


def _client(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[BybitClient, Mock, Mock]:
    session = Mock()
    sleep = Mock()
    monkeypatch.setattr(
        bybit_client_module,
        "HTTP",
        Mock(return_value=session),
    )
    config = Config(
        bybit_api_key="sensitive-api-key",
        bybit_api_secret="sensitive-api-secret",
        bybit_testnet=True,
        trade_journal_path=Path("unused.csv"),
    )
    return BybitClient(config, sleep_fn=sleep), session, sleep


def _failed_request(status_code: int, *, secret: str = "secret") -> Exception:
    return FailedRequestError(
        request=f"GET https://private.example?token={secret}",
        message=f"unsafe {secret}",
        status_code=status_code,
        time="00:00:00",
        resp_headers=None,
    )


def _invalid_request(status_code: int, *, secret: str = "secret") -> Exception:
    return InvalidRequestError(
        request=f"GET https://private.example?token={secret}",
        message=f"unsafe {secret}",
        status_code=status_code,
        time="00:00:00",
        resp_headers=None,
    )


def test_read_timeout_retries_then_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, session, sleep = _client(monkeypatch)
    retry_logger = Mock()
    monkeypatch.setattr(bybit_client_module, "logger", retry_logger)
    expected = {"retCode": 0, "result": {"list": []}}
    session.get_kline.side_effect = [
        requests.ReadTimeout("signed-url-with-secret"),
        expected,
    ]

    result = client.get_klines("linear", "BTCUSDT", "15", 500)

    assert result == expected
    assert session.get_kline.call_count == 2
    sleep.assert_called_once_with(0.5)
    retry_logger.warning.assert_called_once_with(
        "Bybit read retry. Operation=%s Attempt=%s ErrorType=%s",
        "get_klines",
        1,
        "ReadTimeout",
    )
    assert "secret" not in str(retry_logger.mock_calls)


@pytest.mark.parametrize(
    "failure",
    [
        requests.ConnectionError("private connection detail"),
        requests.exceptions.SSLError("private TLS detail"),
    ],
)
def test_connection_or_ssl_error_retries_then_succeeds(
    monkeypatch: pytest.MonkeyPatch,
    failure: Exception,
) -> None:
    client, session, sleep = _client(monkeypatch)
    expected = {"retCode": 0, "result": {"list": []}}
    session.get_positions.side_effect = [
        failure,
        expected,
    ]

    assert client.get_positions("linear", "BTCUSDT") == expected
    assert session.get_positions.call_count == 2
    sleep.assert_called_once_with(0.5)


def test_exhausted_transport_retry_is_typed_and_safe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, session, sleep = _client(monkeypatch)
    session.get_open_orders.side_effect = [
        requests.ReadTimeout("api_key=secret&sign=signature"),
        requests.ReadTimeout("api_key=secret&sign=signature"),
        requests.ReadTimeout("api_key=secret&sign=signature"),
    ]

    with pytest.raises(TemporaryTransportError) as error:
        client.get_open_orders("linear", "BTCUSDT", ORDER_LINK_ID)

    assert session.get_open_orders.call_count == 3
    assert sleep.call_args_list == [call(0.5), call(1.5)]
    assert "get_open_orders" in str(error.value)
    assert "secret" not in str(error.value)
    assert "signature" not in repr(error.value)


@pytest.mark.parametrize(
    "failure",
    [
        _failed_request(503),
        _invalid_request(10000),
        _invalid_request(10016),
        {"retCode": 10000, "retMsg": "unsafe secret"},
    ],
)
def test_temporary_exchange_failure_retries_then_succeeds(
    monkeypatch: pytest.MonkeyPatch,
    failure: object,
) -> None:
    client, session, sleep = _client(monkeypatch)
    expected = {"retCode": 0, "result": {"list": []}}
    session.get_order_history.side_effect = [failure, expected]

    assert (
        client.get_order_history("linear", "BTCUSDT", ORDER_LINK_ID)
        == expected
    )
    sleep.assert_called_once_with(0.5)


def test_temporary_exchange_retry_exhaustion_is_typed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, session, sleep = _client(monkeypatch)
    session.get_closed_pnl.side_effect = [
        _failed_request(500),
        _failed_request(502),
        _failed_request(503),
    ]

    with pytest.raises(TemporaryExchangeError):
        client.get_closed_pnl("linear", "BTCUSDT")

    assert session.get_closed_pnl.call_count == 3
    assert sleep.call_args_list == [call(0.5), call(1.5)]


@pytest.mark.parametrize("status_code", [10003, 10004, 10005, 10001, 10029])
def test_permanent_api_error_is_safe_and_not_retried(
    monkeypatch: pytest.MonkeyPatch,
    status_code: int,
) -> None:
    client, session, sleep = _client(monkeypatch)
    session.get_positions.side_effect = _invalid_request(
        status_code,
        secret="credential-value",
    )

    with pytest.raises(BrokerError) as error:
        client.get_positions("linear", "BTCUSDT")

    session.get_positions.assert_called_once()
    sleep.assert_not_called()
    assert type(error.value) is BrokerError
    assert "credential-value" not in str(error.value)
    assert "private.example" not in repr(error.value)


@pytest.mark.parametrize("failure", [_failed_request(429), _invalid_request(429)])
def test_rate_limit_exhaustion_raises_rate_limit_error(
    monkeypatch: pytest.MonkeyPatch,
    failure: Exception,
) -> None:
    client, session, sleep = _client(monkeypatch)
    session.get_open_orders.side_effect = [failure, failure, failure]

    with pytest.raises(RateLimitError) as error:
        client.list_open_orders("linear", "BTCUSDT")

    assert session.get_open_orders.call_count == 3
    assert sleep.call_args_list == [call(0.5), call(1.5)]
    assert "secret" not in str(error.value)


def test_write_request_is_not_retried(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, session, sleep = _client(monkeypatch)
    timeout = requests.ReadTimeout("unknown write outcome")
    session.place_order.side_effect = timeout

    with pytest.raises(requests.ReadTimeout):
        client.place_order(category="linear", symbol="BTCUSDT")

    session.place_order.assert_called_once()
    sleep.assert_not_called()

    session.cancel_order.side_effect = timeout
    with pytest.raises(requests.ReadTimeout):
        client.cancel_order("linear", "BTCUSDT", ORDER_LINK_ID)

    session.cancel_order.assert_called_once()
    sleep.assert_not_called()


def test_exhausted_read_retry_preserves_pending_and_durable_state(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client, session, sleep = _client(monkeypatch)
    session.get_positions.return_value = {
        "retCode": 0,
        "result": {"list": []},
    }
    session.get_open_orders.return_value = {
        "retCode": 0,
        "result": {"list": []},
    }
    session.place_order.return_value = {
        "retCode": 0,
        "result": {
            "orderId": "exchange-order-1",
            "orderLinkId": ORDER_LINK_ID,
        },
    }
    store = BybitPendingEntryStore(tmp_path / "pending.json")
    broker = BybitBroker(
        client=client,
        category="linear",
        symbol="BTCUSDT",
        pending_entry_store=store,
    )
    setup = Setup(
        index=1,
        timestamp=SIGNAL_TIMESTAMP,
        trend=Trend.BULLISH,
        entry=100.0,
        stop_loss=95.0,
    )
    request = TradeRequest(
        symbol="BTCUSDT",
        decision=Decision.BUY,
        entry=100.0,
        stop_loss=95.0,
        take_profit=110.0,
        volume=1.0,
        setup=setup,
    )
    broker.submit_entry(
        request,
        order_link_id=ORDER_LINK_ID,
        setup_key="stable-setup-key",
        signal_timestamp=SIGNAL_TIMESTAMP,
    )
    broker.drain_pending_entry_events()
    pending_before = broker.get_pending_entry()
    durable_before = store.load()
    session.get_open_orders.reset_mock()
    sleep.reset_mock()
    session.get_open_orders.side_effect = [
        requests.ReadTimeout("secret"),
        requests.ReadTimeout("secret"),
        requests.ReadTimeout("secret"),
    ]

    with pytest.raises(TemporaryTransportError):
        broker.refresh_pending_entry()

    assert session.get_open_orders.call_count == 3
    assert sleep.call_args_list == [call(0.5), call(1.5)]
    assert broker.get_pending_entry() == pending_before
    assert store.load() == durable_before
    assert broker.drain_pending_entry_events() == ()
