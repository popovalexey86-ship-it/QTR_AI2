from pathlib import Path
from unittest.mock import Mock

import pytest

from infrastructure.config import Config
import infrastructure.bybit.bybit_client as bybit_client_module
from infrastructure.bybit.bybit_client import BybitClient


def make_client(
    monkeypatch: pytest.MonkeyPatch,
    *,
    testnet: bool,
) -> tuple[BybitClient, Mock, Mock]:
    session = Mock()
    http_factory = Mock(return_value=session)
    monkeypatch.setattr(bybit_client_module, "HTTP", http_factory)
    config = Config(
        bybit_api_key="sensitive-api-key",
        bybit_api_secret="sensitive-api-secret",
        bybit_testnet=testnet,
        trade_journal_path=Path("unused.csv"),
    )
    return BybitClient(config), session, http_factory


@pytest.mark.parametrize("testnet", [True, False])
def test_is_testnet_is_read_only_and_credentials_are_not_exposed(
    monkeypatch: pytest.MonkeyPatch,
    testnet: bool,
) -> None:
    client, _, http_factory = make_client(monkeypatch, testnet=testnet)

    assert client.is_testnet is testnet
    assert "sensitive-api-key" not in repr(client)
    assert "sensitive-api-secret" not in repr(client)
    with pytest.raises(AttributeError):
        setattr(client, "is_testnet", not testnet)
    http_factory.assert_called_once_with(
        testnet=testnet,
        api_key="sensitive-api-key",
        api_secret="sensitive-api-secret",
    )


def test_pending_order_query_wrappers_use_pybit_argument_names(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, session, _ = make_client(monkeypatch, testnet=True)
    session.get_open_orders.return_value = {"retCode": 0}
    session.get_order_history.return_value = {"retCode": 0}

    assert client.get_open_orders("linear", "BTCUSDT", "QTR-order") == {
        "retCode": 0
    }
    assert client.get_order_history("linear", "BTCUSDT", "QTR-order") == {
        "retCode": 0
    }
    session.get_open_orders.assert_called_once_with(
        category="linear",
        symbol="BTCUSDT",
        orderLinkId="QTR-order",
    )
    session.get_order_history.assert_called_once_with(
        category="linear",
        symbol="BTCUSDT",
        orderLinkId="QTR-order",
    )


def test_open_order_listing_omits_order_link_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, session, _ = make_client(monkeypatch, testnet=True)
    session.get_open_orders.return_value = {"retCode": 0, "result": {"list": []}}

    response = client.list_open_orders("linear", "BTCUSDT")

    assert response == {"retCode": 0, "result": {"list": []}}
    session.get_open_orders.assert_called_once_with(
        category="linear",
        symbol="BTCUSDT",
    )


def test_cancel_order_omits_optional_order_id_when_absent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, session, _ = make_client(monkeypatch, testnet=True)
    session.cancel_order.return_value = {"retCode": 0}

    client.cancel_order("linear", "BTCUSDT", "QTR-order")

    session.cancel_order.assert_called_once_with(
        category="linear",
        symbol="BTCUSDT",
        orderLinkId="QTR-order",
    )


def test_cancel_order_passes_optional_order_id_with_camel_case_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, session, _ = make_client(monkeypatch, testnet=True)
    session.cancel_order.return_value = {"retCode": 0}

    client.cancel_order(
        "linear",
        "BTCUSDT",
        "QTR-order",
        order_id="exchange-order",
    )

    session.cancel_order.assert_called_once_with(
        category="linear",
        symbol="BTCUSDT",
        orderLinkId="QTR-order",
        orderId="exchange-order",
    )
