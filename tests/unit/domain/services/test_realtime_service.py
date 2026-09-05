from datetime import time
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock

import pytest
from SimplyTransport.domain.realtime.enums import OnTimeStatus, ScheduleRelationship
from SimplyTransport.domain.realtime.realtime_schedule.realtime_schedule_model import RealtimeScheduleModel
from SimplyTransport.domain.realtime.realtime_schedule.realtime_schedule_repo import RTStopTimeOverlay
from SimplyTransport.domain.realtime.stop_time.rt_stop_time_model import RTStopTimeModel
from SimplyTransport.domain.schedule.static_schedule_model import StaticScheduleModel
from SimplyTransport.domain.services.realtime_service import RealtimeService
from SimplyTransport.domain.stop_times.stop_time_model import StopTimeModel


@pytest.mark.asyncio
async def test_apply_custom_23_00_sorting_should_return_sorted_list_no_change_normal_times():
    # Arrange
    mock_schedule_data = [
        RealtimeScheduleModel(
            static_schedule=StaticScheduleModel(
                stop_time=StopTimeModel(arrival_time=time.fromisoformat("23:00:00")),
                route=AsyncMock(),
                calendar=AsyncMock(),
                stop=AsyncMock(),
                trip=AsyncMock(),
                is_added_exception=False,
            )
        ),
        RealtimeScheduleModel(
            static_schedule=StaticScheduleModel(
                stop_time=StopTimeModel(arrival_time=time.fromisoformat("00:00:00")),
                route=AsyncMock(),
                calendar=AsyncMock(),
                stop=AsyncMock(),
                trip=AsyncMock(),
                is_added_exception=False,
            )
        ),
        RealtimeScheduleModel(
            static_schedule=StaticScheduleModel(
                stop_time=StopTimeModel(arrival_time=time.fromisoformat("01:00:00")),
                route=AsyncMock(),
                calendar=AsyncMock(),
                stop=AsyncMock(),
                trip=AsyncMock(),
                is_added_exception=False,
            )
        ),
    ]

    real_time_service = RealtimeService(
        rt_stop_repo=AsyncMock(),
        rt_trip_repo=AsyncMock(),
        rt_vehicle_repo=AsyncMock(),
        realtime_schedule_repo=AsyncMock(),
    )

    # Act
    result = await real_time_service.apply_custom_23_00_sorting(mock_schedule_data)

    # Assert
    assert len(result) == len(mock_schedule_data)
    assert result[0] == mock_schedule_data[0]
    assert result[1] == mock_schedule_data[1]
    assert result[2] == mock_schedule_data[2]


@pytest.mark.asyncio
async def test_apply_custom_23_00_sorting_should_return_sorted_list_backwards():
    # Arrange
    mock_schedule_data = [
        RealtimeScheduleModel(
            static_schedule=StaticScheduleModel(
                stop_time=StopTimeModel(arrival_time=time.fromisoformat("01:00:00")),
                route=AsyncMock(),
                calendar=AsyncMock(),
                stop=AsyncMock(),
                trip=AsyncMock(),
                is_added_exception=False,
            )
        ),
        RealtimeScheduleModel(
            static_schedule=StaticScheduleModel(
                stop_time=StopTimeModel(arrival_time=time.fromisoformat("00:00:00")),
                route=AsyncMock(),
                calendar=AsyncMock(),
                stop=AsyncMock(),
                trip=AsyncMock(),
                is_added_exception=False,
            )
        ),
        RealtimeScheduleModel(
            static_schedule=StaticScheduleModel(
                stop_time=StopTimeModel(arrival_time=time.fromisoformat("23:00:00")),
                route=AsyncMock(),
                calendar=AsyncMock(),
                stop=AsyncMock(),
                trip=AsyncMock(),
                is_added_exception=False,
            )
        ),
    ]

    real_time_service = RealtimeService(
        rt_stop_repo=AsyncMock(),
        rt_trip_repo=AsyncMock(),
        rt_vehicle_repo=AsyncMock(),
        realtime_schedule_repo=AsyncMock(),
    )

    # Act
    result = await real_time_service.apply_custom_23_00_sorting(mock_schedule_data)

    # Assert
    assert len(result) == len(mock_schedule_data)
    assert result[0] == mock_schedule_data[2]
    assert result[1] == mock_schedule_data[1]
    assert result[2] == mock_schedule_data[0]


@pytest.mark.asyncio
async def test_get_realtime_schedules_matches_per_stop_stop_time():
    static = StaticScheduleModel(
        stop_time=StopTimeModel(arrival_time=time.fromisoformat("12:00:00"), stop_sequence=1),
        route=AsyncMock(short_name="4"),
        calendar=AsyncMock(),
        stop=AsyncMock(id="S1"),
        trip=AsyncMock(id="T1", dataset="TFI"),
        is_added_exception=False,
    )
    rt_trip = SimpleNamespace(
        trip_id="T1",
        route_id="R1",
        schedule_relationship=ScheduleRelationship.SCHEDULED,
    )
    rt_st = SimpleNamespace(
        trip_id="T1",
        stop_id="S1",
        stop_sequence=1,
        arrival_delay=60,
        departure_delay=60,
        schedule_relationship=ScheduleRelationship.SCHEDULED,
    )
    repo = AsyncMock()
    repo.load_recent_rt_overlay_for_schedules = AsyncMock(
        return_value=(
            {"T1": rt_trip},
            {("T1", "S1", 1): RTStopTimeOverlay(row=cast(RTStopTimeModel, rt_st), exact_match=True)},
        )
    )
    svc = RealtimeService(
        rt_stop_repo=AsyncMock(),
        rt_trip_repo=AsyncMock(),
        rt_vehicle_repo=AsyncMock(),
        realtime_schedule_repo=repo,
    )

    out = await svc.get_realtime_schedules_for_static_schedules([static])

    assert len(out) == 1
    assert out[0].rt_stop_time is rt_st
    assert out[0].rt_trip is rt_trip
    assert out[0].is_trip_removed is False
    assert out[0].delay_in_seconds == 60


@pytest.mark.asyncio
async def test_get_realtime_schedules_trip_removed_without_stop_time_row():
    static = StaticScheduleModel(
        stop_time=StopTimeModel(arrival_time=time.fromisoformat("12:10:00"), stop_sequence=1),
        route=AsyncMock(),
        calendar=AsyncMock(),
        stop=AsyncMock(id="S1"),
        trip=AsyncMock(id="T1", dataset="TFI"),
        is_added_exception=False,
    )
    rt_trip = SimpleNamespace(
        trip_id="T1",
        route_id="R1",
        schedule_relationship=ScheduleRelationship.CANCELED,
    )
    repo = AsyncMock()
    repo.load_recent_rt_overlay_for_schedules = AsyncMock(return_value=({"T1": rt_trip}, {}))
    svc = RealtimeService(
        rt_stop_repo=AsyncMock(),
        rt_trip_repo=AsyncMock(),
        rt_vehicle_repo=AsyncMock(),
        realtime_schedule_repo=repo,
    )

    out = await svc.get_realtime_schedules_for_static_schedules([static])

    assert len(out) == 1
    assert out[0].is_trip_removed is True
    assert out[0].rt_stop_time is None
    assert out[0].rt_trip is rt_trip


@pytest.mark.asyncio
async def test_get_realtime_schedules_exact_skipped_stop():
    static = StaticScheduleModel(
        stop_time=StopTimeModel(arrival_time=time.fromisoformat("12:00:00"), stop_sequence=10),
        route=AsyncMock(short_name="4"),
        calendar=AsyncMock(),
        stop=AsyncMock(id="S10"),
        trip=AsyncMock(id="T1", dataset="TFI"),
        is_added_exception=False,
    )
    rt_st = SimpleNamespace(
        trip_id="T1",
        stop_id="S10",
        stop_sequence=10,
        arrival_delay=None,
        departure_delay=None,
        schedule_relationship=ScheduleRelationship.SKIPPED,
    )
    repo = AsyncMock()
    repo.load_recent_rt_overlay_for_schedules = AsyncMock(
        return_value=(
            {},
            {("T1", "S10", 10): RTStopTimeOverlay(row=cast(RTStopTimeModel, rt_st), exact_match=True)},
        )
    )
    svc = RealtimeService(
        rt_stop_repo=AsyncMock(),
        rt_trip_repo=AsyncMock(),
        rt_vehicle_repo=AsyncMock(),
        realtime_schedule_repo=repo,
    )

    out = await svc.get_realtime_schedules_for_static_schedules([static])

    assert len(out) == 1
    assert out[0].delay == "Skipped"
    assert out[0].on_time_status is OnTimeStatus.SKIPPED
    assert out[0].rt_stop_overlay_exact is True


@pytest.mark.asyncio
async def test_get_realtime_schedules_non_exact_skipped_predecessor_not_shown_as_skipped():
    static = StaticScheduleModel(
        stop_time=StopTimeModel(arrival_time=time.fromisoformat("12:30:00"), stop_sequence=10),
        route=AsyncMock(short_name="4"),
        calendar=AsyncMock(),
        stop=AsyncMock(id="S10"),
        trip=AsyncMock(id="T1", dataset="TFI"),
        is_added_exception=False,
    )
    rt_st = SimpleNamespace(
        trip_id="T1",
        stop_id="S5",
        stop_sequence=5,
        arrival_delay=300,
        departure_delay=300,
        schedule_relationship=ScheduleRelationship.SCHEDULED,
    )
    repo = AsyncMock()
    repo.load_recent_rt_overlay_for_schedules = AsyncMock(
        return_value=(
            {},
            {("T1", "S10", 10): RTStopTimeOverlay(row=cast(RTStopTimeModel, rt_st), exact_match=False)},
        )
    )
    svc = RealtimeService(
        rt_stop_repo=AsyncMock(),
        rt_trip_repo=AsyncMock(),
        rt_vehicle_repo=AsyncMock(),
        realtime_schedule_repo=repo,
    )

    out = await svc.get_realtime_schedules_for_static_schedules([static])

    assert len(out) == 1
    assert out[0].delay_in_seconds == 300
    assert out[0].on_time_status is not OnTimeStatus.SKIPPED
