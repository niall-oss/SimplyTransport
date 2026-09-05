from datetime import time
from unittest.mock import AsyncMock

import pytest
from SimplyTransport.domain.enums import DayOfWeek
from SimplyTransport.domain.schedule.schedule_repo import ScheduleRepo, _arrival_time_conditions
from SimplyTransport.domain.stop_times.stop_time_model import StopTimeModel


def test_arrival_time_conditions_empty_when_either_bound_missing():
    assert _arrival_time_conditions(None, None) == []
    assert _arrival_time_conditions(time(8, 0), None) == []
    assert _arrival_time_conditions(None, time(9, 0)) == []


def test_arrival_time_conditions_wraps_overnight_window():
    start = time(23, 0)
    end = time(1, 0)
    conditions = _arrival_time_conditions(start, end)
    assert len(conditions) == 1


def test_arrival_time_conditions_uses_inclusive_same_day_window():
    start = time(8, 0)
    end = time(9, 0)
    conditions = _arrival_time_conditions(start, end)
    assert len(conditions) == 2


def test_stop_time_is_active_between_times_wraps_midnight():
    stop_time = StopTimeModel(
        arrival_time=time(23, 50),
        departure_time=time(23, 50),
        trip_id="t",
        stop_id="s",
        stop_sequence=1,
        dataset="TFI",
    )
    assert stop_time.is_active_between_times(time(23, 0), time(1, 0)) is True
    assert stop_time.is_active_between_times(time(0, 0), time(1, 0)) is False
    assert (
        StopTimeModel(
            arrival_time=time(0, 10),
            departure_time=time(0, 10),
            trip_id="t",
            stop_id="s",
            stop_sequence=1,
            dataset="TFI",
        ).is_active_between_times(time(23, 0), time(1, 0))
        is True
    )
    assert (
        StopTimeModel(
            arrival_time=time(12, 0),
            departure_time=time(12, 0),
            trip_id="t",
            stop_id="s",
            stop_sequence=1,
            dataset="TFI",
        ).is_active_between_times(time(11, 0), time(13, 0))
        is True
    )


@pytest.mark.asyncio
async def test_get_static_schedules_rejects_invalid_day():
    repo = ScheduleRepo(session=None)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="Invalid day of week"):
        await repo.get_static_schedules(day=cast_invalid_day())


@pytest.mark.asyncio
async def test_get_static_schedules_for_service_ids_empty_list():
    repo = ScheduleRepo(session=AsyncMock())
    assert await repo.get_static_schedules_for_service_ids([]) == []


def cast_invalid_day() -> DayOfWeek:
    return 99  # type: ignore[return-value]
