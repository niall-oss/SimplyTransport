from datetime import time
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from freezegun import freeze_time
from SimplyTransport.domain.realtime.enums import ScheduleRelationship
from SimplyTransport.domain.realtime.realtime_schedule.realtime_schedule_repo import RTStopTimeOverlay
from SimplyTransport.domain.schedule.static_schedule_model import StaticScheduleModel
from SimplyTransport.timescale.services.delays_service import (
    DelaysService,
    delay_recording_cache_key,
    due_delay_records,
)


def _static(*, trip_id: str = "T1", stop_id: str = "S1", arrival: time = time(12, 0), sequence: int = 1):
    route = MagicMock()
    route.short_name = "4"
    stop_time = MagicMock()
    stop_time.arrival_time = arrival
    stop_time.stop_sequence = sequence
    stop = MagicMock()
    stop.id = stop_id
    trip = MagicMock()
    trip.id = trip_id
    return StaticScheduleModel(
        route=route,
        stop_time=stop_time,
        calendar=MagicMock(),
        stop=stop,
        trip=trip,
        is_added_exception=False,
    )


def _overlay(*, delay: int = 360, rel: str = ScheduleRelationship.SCHEDULED, exact: bool = True):
    row = SimpleNamespace(arrival_delay=delay, departure_delay=delay, schedule_relationship=rel)
    return RTStopTimeOverlay(row=row, exact_match=exact)  # type: ignore[arg-type]


def _service() -> tuple[DelaysService, dict[str, Any]]:
    static = _static()
    overlay = _overlay()
    deps = {
        "ts_stop_time_repo": AsyncMock(),
        "schedule_service": AsyncMock(),
        "realtime_service": AsyncMock(),
        "redis_cache": AsyncMock(),
    }
    deps["schedule_service"].get_all_schedule_for_day_between_times = AsyncMock(return_value=[static])
    deps["schedule_service"].remove_exceptions_and_inactive_calendars = AsyncMock(return_value=[static])
    deps["schedule_service"].add_in_added_exceptions = AsyncMock(return_value=[static])
    deps["realtime_service"].get_distinct_realtime_trips = AsyncMock(return_value=["T1"])
    deps["realtime_service"].load_recent_rt_overlay_for_schedules = AsyncMock(
        return_value=({}, {("T1", "S1", 1): overlay})
    )
    deps["redis_cache"].check_keys_exist = AsyncMock(return_value={})
    return DelaysService(**deps), deps


@freeze_time("2025-03-21 12:06:30")
def test_due_delay_records_keeps_just_arrived_overlay():
    static = _static()
    records = due_delay_records([static], {}, {("T1", "S1", 1): _overlay(delay=360)})
    assert len(records) == 1
    assert records[0].stop_id == "S1"
    assert records[0].route_code == "4"
    assert records[0].scheduled_time == time(12, 0)
    assert records[0].delay_in_seconds == 360


@freeze_time("2025-03-21 12:08:00")
def test_due_delay_records_skips_when_more_than_a_minute_past():
    static = _static()
    records = due_delay_records([static], {}, {("T1", "S1", 1): _overlay(delay=360)})
    assert records == []


@freeze_time("2025-03-21 12:06:30")
def test_due_delay_records_skips_cancelled_trips():
    static = _static()
    trip = SimpleNamespace(schedule_relationship=ScheduleRelationship.CANCELED)
    records = due_delay_records(
        [static],
        {"T1": trip},  # type: ignore[dict-item]
        {("T1", "S1", 1): _overlay(delay=360)},
    )
    assert records == []


@freeze_time("2025-03-21 12:00:30")
def test_due_delay_records_skips_exact_skipped_stops():
    static = _static()
    records = due_delay_records(
        [static],
        {},
        {("T1", "S1", 1): _overlay(delay=0, rel=ScheduleRelationship.SKIPPED, exact=True)},
    )
    assert records == []


@freeze_time("2025-03-21 12:06:30")
@pytest.mark.asyncio
async def test_record_all_delays_loads_overlay_once():
    svc, deps = _service()
    recorded = await svc.record_all_delays()
    assert recorded == 1
    schedules = deps["schedule_service"].add_in_added_exceptions.return_value
    deps["realtime_service"].load_recent_rt_overlay_for_schedules.assert_awaited_once_with(schedules)
    deps["realtime_service"].get_realtime_schedules_for_static_schedules.assert_not_called()
    inserted = deps["ts_stop_time_repo"].bulk_insert_delay_records.await_args.args[0]
    assert len(inserted) == 1
    assert inserted[0].delay_in_seconds == 360


@freeze_time("2025-03-21 12:06:30")
@pytest.mark.asyncio
async def test_record_all_delays_skips_keys_already_in_redis():
    svc, deps = _service()
    key = delay_recording_cache_key("4", "S1", time(12, 0))
    deps["redis_cache"].check_keys_exist = AsyncMock(return_value={key: True})
    recorded = await svc.record_all_delays()
    assert recorded == 0
    inserted = deps["ts_stop_time_repo"].bulk_insert_delay_records.await_args.args[0]
    assert inserted == []
    deps["redis_cache"].set_many_empty_keys.assert_awaited_once_with([], expiration=60 * 5)


@freeze_time("2025-03-21 12:08:00")
@pytest.mark.asyncio
async def test_record_all_delays_records_zero_when_nothing_is_due():
    svc, deps = _service()
    recorded = await svc.record_all_delays()
    assert recorded == 0
    inserted = deps["ts_stop_time_repo"].bulk_insert_delay_records.await_args.args[0]
    assert inserted == []


@pytest.mark.asyncio
async def test_cleanup_old_delays_delegates_to_repo():
    svc, deps = _service()
    deps["ts_stop_time_repo"].delete_old_delays = AsyncMock(return_value=4)
    assert await svc.cleanup_old_delays() == 4
    deps["ts_stop_time_repo"].delete_old_delays.assert_awaited_once()
