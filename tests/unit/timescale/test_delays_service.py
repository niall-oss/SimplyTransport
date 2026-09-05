from datetime import time
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock

import pytest
from SimplyTransport.domain.realtime.realtime_schedule.realtime_schedule_model import RealtimeScheduleModel
from SimplyTransport.domain.schedule.static_schedule_model import StaticScheduleModel
from SimplyTransport.timescale.services.delays_service import DelaysService


def _schedule() -> RealtimeScheduleModel:
    route = MagicMock()
    route.short_name = "4"
    stop_time = MagicMock()
    stop_time.arrival_time = time(8, 0)
    stop = MagicMock()
    stop.id = "S1"
    static = StaticScheduleModel(
        route=route,
        stop_time=stop_time,
        calendar=MagicMock(),
        stop=stop,
        trip=MagicMock(),
        is_added_exception=False,
    )
    return cast(RealtimeScheduleModel, SimpleNamespace(static_schedule=static, delay_in_seconds=90))


def _service() -> tuple[DelaysService, dict[str, Any]]:
    deps = {
        "ts_stop_time_repo": AsyncMock(),
        "schedule_service": AsyncMock(),
        "realtime_service": AsyncMock(),
        "redis_cache": AsyncMock(),
    }
    deps["schedule_service"].get_all_schedule_for_day_between_times = AsyncMock(return_value=["static"])
    deps["schedule_service"].remove_exceptions_and_inactive_calendars = AsyncMock(return_value=["static"])
    deps["schedule_service"].add_in_added_exceptions = AsyncMock(return_value=["static"])
    deps["realtime_service"].get_distinct_realtime_trips = AsyncMock(return_value=["T1"])
    deps["realtime_service"].get_realtime_schedules_for_static_schedules = AsyncMock(
        return_value=[_schedule()]
    )
    deps["realtime_service"].filter_to_only_due_schedules = MagicMock(side_effect=lambda rows: rows)
    deps["realtime_service"].filter_to_only_schedules_with_updates = MagicMock(side_effect=lambda rows: rows)
    return DelaysService(**deps), deps


@pytest.mark.asyncio
async def test_record_all_delays_skips_keys_already_in_redis():
    svc, deps = _service()
    schedule = _schedule()
    key = svc.create_cache_key_for_schedule(schedule)
    deps["redis_cache"].check_keys_exist = AsyncMock(return_value={key: True})
    recorded = await svc.record_all_delays()
    assert recorded == 0
    deps["ts_stop_time_repo"].bulk_insert_delay_records.assert_awaited_once()
    inserted = deps["ts_stop_time_repo"].bulk_insert_delay_records.await_args.args[0]
    assert inserted == []
    deps["redis_cache"].set_many_empty_keys.assert_awaited_once_with([], expiration=60 * 5)


@pytest.mark.asyncio
async def test_record_all_delays_inserts_on_cache_miss():
    svc, deps = _service()
    schedule = _schedule()
    key = svc.create_cache_key_for_schedule(schedule)
    deps["redis_cache"].check_keys_exist = AsyncMock(return_value={key: False})
    recorded = await svc.record_all_delays()
    assert recorded == 1
    inserted = deps["ts_stop_time_repo"].bulk_insert_delay_records.await_args.args[0]
    assert len(inserted) == 1
    assert inserted[0].stop_id == "S1"
    assert inserted[0].route_code == "4"
    assert inserted[0].delay_in_seconds == 90
    deps["redis_cache"].set_many_empty_keys.assert_awaited_once()
    assert deps["redis_cache"].set_many_empty_keys.await_args.args[0] == [key]


@pytest.mark.asyncio
async def test_record_all_delays_records_zero_when_filters_drop_all():
    svc, deps = _service()
    deps["realtime_service"].filter_to_only_due_schedules = MagicMock(return_value=[])
    deps["realtime_service"].filter_to_only_schedules_with_updates = MagicMock(return_value=[])
    deps["redis_cache"].check_keys_exist = AsyncMock(return_value={})
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
