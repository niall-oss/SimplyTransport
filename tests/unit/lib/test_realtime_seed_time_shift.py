from datetime import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from freezegun import freeze_time
from SimplyTransport.lib import realtime_seed_time_shift as seed


def _stop_time(arrival: time, sequence: int = 1) -> SimpleNamespace:
    return SimpleNamespace(arrival_time=arrival, departure_time=arrival, stop_sequence=sequence)


def _execute_result_for_stop_times(rows: list) -> MagicMock:
    result = MagicMock()
    result.scalars.return_value.all.return_value = rows
    return result


@pytest.mark.asyncio
async def test_shift_returns_none_when_payload_has_no_trip_updates():
    session = AsyncMock()
    assert await seed.shift_db_stop_times_and_patch_payload_for_now(session, "TFI", {"entity": []}) is None
    session.execute.assert_not_awaited()


@pytest.mark.asyncio
@freeze_time("2026-03-21 12:00:00")
async def test_shift_warns_when_no_active_calendar_and_still_moves_times(capsys):
    first = _stop_time(time(8, 0), 1)
    second = _stop_time(time(8, 10), 2)
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_execute_result_for_stop_times([first, second]))
    session.commit = AsyncMock()
    payload = {
        "entity": [
            {
                "trip_update": {
                    "trip": {"trip_id": "T1", "start_time": "08:00:00", "start_date": "20250321"},
                    "trip_properties": {"trip_id": "T1"},
                }
            }
        ]
    }
    with patch.object(seed, "_service_id_active_on_local_today", AsyncMock(return_value=None)):
        service_id = await seed.shift_db_stop_times_and_patch_payload_for_now(session, "TFI", payload)

    assert service_id is None
    assert "no calendar row" in capsys.readouterr().out
    assert first.arrival_time == time(12, 2)
    assert second.arrival_time == time(12, 12)
    trip = payload["entity"][0]["trip_update"]["trip"]
    assert trip["start_time"] == "12:02:00"
    assert trip["start_date"] == "20260321"
    props = payload["entity"][0]["trip_update"]["trip_properties"]
    assert props["start_time"] == "12:02:00"
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_shift_repoints_trips_to_active_calendar():
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_execute_result_for_stop_times([]))
    session.commit = AsyncMock()
    payload = {"entity": [{"trip_update": {"trip": {"trip_id": "T1"}}}]}
    with patch.object(seed, "_service_id_active_on_local_today", AsyncMock(return_value="svc-today")):
        assert (
            await seed.shift_db_stop_times_and_patch_payload_for_now(session, "TFI", payload) == "svc-today"
        )
    assert session.execute.await_count >= 2
