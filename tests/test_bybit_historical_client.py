from datetime import UTC, datetime, timedelta
from unittest.mock import Mock

import pytest

from infrastructure.bybit.bybit_historical_client import (
    BybitHistoricalClient,
    MAX_PAGE_SIZE,
)
from infrastructure.bybit.bybit_historical_mapper import HistoricalDataError


START = datetime(2025, 1, 1, tzinfo=UTC)


def row(minute: int, *, volume: str = "10") -> list[str]:
    timestamp = int((START + timedelta(minutes=minute)).timestamp() * 1000)
    return [str(timestamp), "100", "110", "90", "105", volume, "0"]


def response(rows, ret_code=0):
    result = Mock()
    result.json.return_value = {
        "retCode": ret_code,
        "result": {"list": rows},
    }
    return result


def client_with_pages(*pages, now=START + timedelta(days=1)):
    session = Mock()
    session.get.side_effect = [response(page) for page in pages]
    client = BybitHistoricalClient(session=session, clock=lambda: now)
    return client, session


def fetch(client, *, start=START, end=START + timedelta(minutes=4), interval="1"):
    return client.fetch_candles(
        category="linear",
        symbol="BTCUSDT",
        interval=interval,
        start=start,
        end=end,
    )


def test_reverse_rows_are_sorted_and_receive_stable_indices():
    client, _ = client_with_pages([row(2), row(1), row(0)])

    candles = fetch(client, end=START + timedelta(minutes=3))

    assert [candle.timestamp for candle in candles] == [
        START,
        START + timedelta(minutes=1),
        START + timedelta(minutes=2),
    ]
    assert [candle.index for candle in candles] == [0, 1, 2]
    assert candles[0].open == 100.0
    assert candles[0].high == 110.0
    assert candles[0].low == 90.0
    assert candles[0].close == 105.0
    assert candles[0].volume == 10.0
    assert candles[0].timestamp.tzinfo is UTC


def test_pagination_deduplicates_page_boundaries_and_uses_limit_1000():
    client, session = client_with_pages(
        [row(3), row(2)],
        [row(2), row(1), row(0)],
    )

    candles = fetch(client)

    assert [candle.timestamp for candle in candles] == [
        START + timedelta(minutes=minute) for minute in range(4)
    ]
    assert session.get.call_count == 2
    assert all(
        call.kwargs["params"]["limit"] == MAX_PAGE_SIZE
        for call in session.get.call_args_list
    )
    assert session.get.call_args_list[1].kwargs["params"]["end"] < (
        session.get.call_args_list[0].kwargs["params"]["end"]
    )


def test_exact_half_open_range_filtering():
    client, _ = client_with_pages([row(3), row(2), row(1), row(0)])

    candles = fetch(
        client,
        start=START + timedelta(minutes=1),
        end=START + timedelta(minutes=3),
    )

    assert [candle.timestamp for candle in candles] == [
        START + timedelta(minutes=1),
        START + timedelta(minutes=2),
    ]


@pytest.mark.parametrize(
    "bad_row",
    [
        ["missing"],
        ["bad", "100", "110", "90", "105", "1"],
        row(0, volume="-1"),
        [row(0)[0], "100", "99", "90", "105", "1"],
        [row(0)[0], "100", "110", "106", "105", "1"],
    ],
)
def test_malformed_or_invalid_rows_are_rejected(bad_row):
    client, _ = client_with_pages([bad_row])

    with pytest.raises(HistoricalDataError):
        fetch(client)


def test_nonzero_ret_code_is_rejected_without_raw_response():
    session = Mock()
    session.get.return_value = response([], ret_code=10001)
    client = BybitHistoricalClient(
        session=session,
        clock=lambda: START + timedelta(days=1),
    )

    with pytest.raises(HistoricalDataError) as error:
        fetch(client)

    assert "10001" not in str(error.value)


def test_unsupported_interval_is_rejected_without_http():
    client, session = client_with_pages([])

    with pytest.raises(HistoricalDataError, match="Unsupported"):
        fetch(client, interval="2")

    session.get.assert_not_called()


@pytest.mark.parametrize(
    "category, symbol",
    [("spot", "BTCUSDT"), ("linear", "btcusdt"), ("linear", "BTC-USDT")],
)
def test_unsupported_category_or_symbol_is_rejected(category, symbol):
    client, session = client_with_pages([])

    with pytest.raises(HistoricalDataError):
        client.fetch_candles(
            category=category,
            symbol=symbol,
            interval="1",
            start=START,
            end=START + timedelta(minutes=1),
        )

    session.get.assert_not_called()


def test_naive_datetime_is_rejected_without_http():
    client, session = client_with_pages([])

    with pytest.raises(HistoricalDataError, match="timezone-aware UTC"):
        fetch(client, start=datetime(2025, 1, 1))

    session.get.assert_not_called()


def test_start_at_or_after_end_is_rejected():
    client, _ = client_with_pages([])

    with pytest.raises(HistoricalDataError, match="earlier than end"):
        fetch(client, start=START, end=START)


def test_non_advancing_pagination_cursor_is_rejected():
    client, _ = client_with_pages([row(3), row(2)], [row(2)])

    with pytest.raises(HistoricalDataError, match="did not advance"):
        fetch(client)


def test_empty_page_stops_pagination_safely():
    client, session = client_with_pages([])

    assert fetch(client) == ()
    assert session.get.call_count == 1


def test_unfinished_final_candle_is_excluded():
    now = START + timedelta(minutes=3, seconds=30)
    client, _ = client_with_pages([row(3), row(2)], [], now=now)

    candles = fetch(client, end=START + timedelta(minutes=4))

    assert [candle.timestamp for candle in candles] == [
        START + timedelta(minutes=2)
    ]
