from datetime import UTC, date, datetime, time
from json import JSONDecodeError
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from SimplyTransport.lib import gtfs_realtime_importers as rt

URL = "https://example.test/gtfs-rt"
API_KEY = "test-key"
HEADERS = {"Cache-Control": "no-cache", "x-api-key": API_KEY}


def _json_response(status_code: int, payload: dict | None = None) -> MagicMock:
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = payload if payload is not None else {"entity": []}
    return response


def _invalid_json_response() -> MagicMock:
    response = MagicMock()
    response.status_code = 200
    response.json.side_effect = JSONDecodeError("Expecting value", "", 0)
    return response


def _mock_async_client(get_side_effect: list) -> tuple[AsyncMock, AsyncMock]:
    client = AsyncMock()
    client.get = AsyncMock(side_effect=get_side_effect)
    client_cm = AsyncMock()
    client_cm.__aenter__.return_value = client
    client_cm.__aexit__.return_value = None
    return client, client_cm


@pytest.mark.asyncio
async def test_fetch_succeeds_on_first_try():
    payload = {"entity": [{"id": "1"}]}
    client, client_cm = _mock_async_client([_json_response(200, payload)])

    with (
        patch.object(rt.httpx, "AsyncClient", return_value=client_cm) as async_client_cls,
        patch.object(rt.asyncio, "sleep", new_callable=AsyncMock) as sleep,
    ):
        result = await rt._fetch_realtime_json(URL, API_KEY)
        async_client_cls.assert_called_once_with(timeout=rt.HTTP_TIMEOUT_SECONDS)

    assert result == payload
    client.get.assert_awaited_once_with(URL, headers=HEADERS)
    sleep.assert_not_awaited()


@pytest.mark.asyncio
async def test_fetch_retries_500_then_succeeds():
    payload = {"entity": []}
    client, client_cm = _mock_async_client(
        [_json_response(500), _json_response(200, payload)],
    )

    with (
        patch.object(rt.httpx, "AsyncClient", return_value=client_cm),
        patch.object(rt.asyncio, "sleep", new_callable=AsyncMock) as sleep,
    ):
        result = await rt._fetch_realtime_json(URL, API_KEY)

    assert result == payload
    assert client.get.await_count == 2
    sleep.assert_awaited_once_with(rt.HTTP_RETRY_DELAY_SECONDS)


@pytest.mark.asyncio
async def test_fetch_exhausts_retries_on_500():
    client, client_cm = _mock_async_client(
        [_json_response(500), _json_response(500), _json_response(500)],
    )

    with (
        patch.object(rt.httpx, "AsyncClient", return_value=client_cm),
        patch.object(rt.asyncio, "sleep", new_callable=AsyncMock) as sleep,
    ):
        result = await rt._fetch_realtime_json(URL, API_KEY)

    assert result is None
    assert client.get.await_count == rt.HTTP_MAX_ATTEMPTS
    assert sleep.await_count == rt.HTTP_MAX_RETRIES


@pytest.mark.asyncio
async def test_fetch_retries_timeout_then_succeeds():
    payload = {"entity": []}
    client, client_cm = _mock_async_client(
        [httpx.TimeoutException("timed out"), _json_response(200, payload)],
    )

    with (
        patch.object(rt.httpx, "AsyncClient", return_value=client_cm),
        patch.object(rt.asyncio, "sleep", new_callable=AsyncMock) as sleep,
    ):
        result = await rt._fetch_realtime_json(URL, API_KEY)

    assert result == payload
    assert client.get.await_count == 2
    sleep.assert_awaited_once_with(rt.HTTP_RETRY_DELAY_SECONDS)


@pytest.mark.asyncio
async def test_fetch_does_not_retry_400():
    client, client_cm = _mock_async_client([_json_response(400)])

    with (
        patch.object(rt.httpx, "AsyncClient", return_value=client_cm),
        patch.object(rt.asyncio, "sleep", new_callable=AsyncMock) as sleep,
    ):
        result = await rt._fetch_realtime_json(URL, API_KEY)

    assert result is None
    client.get.assert_awaited_once()
    sleep.assert_not_awaited()


@pytest.mark.asyncio
async def test_fetch_retries_invalid_json_then_succeeds():
    payload = {"entity": []}
    client, client_cm = _mock_async_client(
        [_invalid_json_response(), _json_response(200, payload)],
    )

    with (
        patch.object(rt.httpx, "AsyncClient", return_value=client_cm),
        patch.object(rt.asyncio, "sleep", new_callable=AsyncMock) as sleep,
    ):
        result = await rt._fetch_realtime_json(URL, API_KEY)

    assert result == payload
    assert client.get.await_count == 2
    sleep.assert_awaited_once_with(rt.HTTP_RETRY_DELAY_SECONDS)


def test_rt_trip_record_column_order():
    created = datetime(2026, 9, 4, 1, 0, tzinfo=UTC)
    assert rt.rt_trip_record(
        "t1",
        "r1",
        time(8, 30),
        date(2026, 9, 4),
        "SCHEDULED",
        1,
        "entity-1",
        "TFI",
        created,
    ) == ("t1", "r1", time(8, 30), date(2026, 9, 4), "SCHEDULED", 1, "entity-1", "TFI", created)


def test_rt_stop_time_record_allows_null_delays():
    created = datetime(2026, 9, 4, 1, 0, tzinfo=UTC)
    assert rt.rt_stop_time_record(
        "s1",
        "t1",
        3,
        "SCHEDULED",
        None,
        12,
        "entity-1",
        "TFI",
        created,
    ) == ("s1", "t1", 3, "SCHEDULED", None, 12, "entity-1", "TFI", created)


def test_rt_vehicle_record_column_order():
    created = datetime(2026, 9, 4, 1, 0, tzinfo=UTC)
    updated = datetime(2026, 9, 4, 0, 59)
    assert rt.rt_vehicle_record(9, "t1", updated, 53.3, -6.2, "TFI", created) == (
        9,
        "t1",
        updated,
        53.3,
        -6.2,
        "TFI",
        created,
    )


def test_dedup_records_by_key_keeps_last():
    first = ("t1", "r1", "a")
    second = ("t1", "r1", "b")
    other = ("t2", "r1", "c")
    assert rt.dedup_records_by_key([first, other, second], (0, 1)) == [second, other]
