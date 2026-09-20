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


def test_effective_trip_id_uses_properties_for_duplicated():
    assert (
        rt._effective_trip_id_for_trip_update(
            {
                "trip": {"trip_id": "descriptor", "schedule_relationship": "DUPLICATED"},
                "trip_properties": {"trip_id": "actual-trip"},
            }
        )
        == "actual-trip"
    )
    assert rt._effective_trip_id_for_trip_update({"trip": {"trip_id": "t1"}}) == "t1"
    assert rt._effective_trip_id_for_trip_update({"trip": {}}) is None


def test_skip_stop_time_import_for_removed_trips():
    assert rt._skip_stop_time_import_for_trip_relationship("CANCELED") is True
    assert rt._skip_stop_time_import_for_trip_relationship("DELETED") is True
    assert rt._skip_stop_time_import_for_trip_relationship("SCHEDULED") is False


def _trip_update_payload() -> dict:
    return {
        "entity": [
            {
                "id": "unknown-trip",
                "trip_update": {
                    "trip": {"trip_id": "MISSING"},
                    "stop_time_update": [{"stop_id": "S1", "stop_sequence": 1}],
                },
            },
            {
                "id": "ok",
                "trip_update": {
                    "trip": {"trip_id": "T1", "route_id": "FEED_R", "direction_id": 1},
                    "stop_time_update": [
                        {"stop_id": "S1"},
                        {"stop_id": "S1", "stop_sequence": "bad"},
                        {"stop_id": "missing-stop", "stop_sequence": 2},
                        {
                            "stop_id": "S1",
                            "stop_sequence": 3,
                            "arrival": {"delay": 10},
                            "departure": {"delay": 12},
                        },
                    ],
                },
            },
        ]
    }


def test_collect_trip_update_feed_ids_includes_cancelled_trips():
    data = {
        "entity": [
            {
                "id": "cancelled",
                "trip_update": {
                    "trip": {"trip_id": "T1", "schedule_relationship": "CANCELED"},
                    "stop_time_update": [{"stop_id": "S1", "stop_sequence": 1}],
                },
            },
            {
                "id": "ok",
                "trip_update": {
                    "trip": {"trip_id": "T2"},
                    "stop_time_update": [{"stop_id": "S2", "stop_sequence": 1}],
                },
            },
        ]
    }
    trip_ids, stop_ids = rt.collect_trip_update_feed_ids(data)
    assert trip_ids == {"T1", "T2"}
    assert stop_ids == {"S2"}


def test_build_records_skips_unknown_trip_and_bad_sequence():
    trips, stops = rt.build_rt_trip_and_stop_time_records(
        _trip_update_payload(),
        "TFI",
        {"T1": ("STATIC_R", 0)},
        frozenset({"S1"}),
    )
    assert len(trips) == 1
    assert trips[0][0] == "T1"
    assert trips[0][1] == "FEED_R"
    assert trips[0][4] == "SCHEDULED"
    assert len(stops) == 1
    assert stops[0][0] == "S1"
    assert stops[0][1] == "T1"
    assert stops[0][2] == 3


def test_build_records_imports_cancelled_trip_without_stop_times():
    data = {
        "entity": [
            {
                "id": "cancelled",
                "trip_update": {
                    "trip": {"trip_id": "T1", "schedule_relationship": "CANCELED", "route_id": "R1"},
                    "stop_time_update": [{"stop_id": "S1", "stop_sequence": 1}],
                },
            }
        ]
    }
    trips, stops = rt.build_rt_trip_and_stop_time_records(data, "TFI", {"T1": ("R1", 0)}, frozenset({"S1"}))
    assert len(trips) == 1
    assert trips[0][4] == "CANCELED"
    assert stops == []


def test_build_records_uses_duplicated_property_trip_id():
    data = {
        "entity": [
            {
                "id": "dup",
                "trip_update": {
                    "trip": {
                        "trip_id": "descriptor",
                        "schedule_relationship": "DUPLICATED",
                        "route_id": "R1",
                    },
                    "trip_properties": {"trip_id": "T1"},
                    "stop_time_update": [{"stop_id": "S1", "stop_sequence": 1, "arrival": {"delay": 5}}],
                },
            }
        ]
    }
    trips, stops = rt.build_rt_trip_and_stop_time_records(data, "TFI", {"T1": ("R1", 0)}, frozenset({"S1"}))
    assert trips[0][0] == "T1"
    assert stops[0][1] == "T1"


def test_build_rt_vehicle_records_skips_unknown_trips_and_uses_utc():
    data = {
        "entity": [
            {
                "id": "ok",
                "vehicle": {
                    "trip": {"trip_id": "T1"},
                    "vehicle": {"id": "9"},
                    "timestamp": "1705880460",
                    "position": {"latitude": 53.3, "longitude": -6.2},
                },
            },
            {
                "id": "unknown",
                "vehicle": {
                    "trip": {"trip_id": "MISSING"},
                    "vehicle": {"id": "10"},
                    "timestamp": "1705880460",
                    "position": {"latitude": 53.3, "longitude": -6.2},
                },
            },
        ]
    }
    records = rt.build_rt_vehicle_records(data, "TFI", {"T1": ("R1", 0)})
    assert len(records) == 1
    assert records[0][0] == 9
    assert records[0][1] == "T1"
    assert records[0][2] == datetime.fromtimestamp(1705880460, tz=UTC).replace(tzinfo=None)


@pytest.mark.asyncio
async def test_load_shared_context_skips_query_when_no_trip_ids():
    with patch.object(rt, "async_session_factory") as factory:
        ctx = await rt.load_realtime_import_shared_context("TFI", set())
    assert ctx.trip_dir == {}
    factory.assert_not_called()


@pytest.mark.asyncio
async def test_load_shared_context_queries_feed_trip_ids_only():
    row = MagicMock()
    row.id = "T1"
    row.route_id = "R1"
    row.direction = 0
    result = MagicMock()
    result.all.return_value = [row]
    session = AsyncMock()
    session.execute = AsyncMock(return_value=result)
    session_cm = AsyncMock()
    session_cm.__aenter__.return_value = session
    session_cm.__aexit__.return_value = None

    with patch.object(rt, "async_session_factory", return_value=session_cm):
        ctx = await rt.load_realtime_import_shared_context("TFI", {"T1", "T2"})

    assert ctx.trip_dir == {"T1": ("R1", 0)}
    stmt = session.execute.await_args.args[0]
    compiled = str(stmt.compile(compile_kwargs={"render_postcompile": True}))
    assert "IN" in compiled
    assert "dataset" in compiled.lower()
