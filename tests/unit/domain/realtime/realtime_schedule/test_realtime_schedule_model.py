from datetime import time
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock

from freezegun import freeze_time
from SimplyTransport.domain.realtime.enums import OnTimeStatus, ScheduleRelationship
from SimplyTransport.domain.realtime.realtime_schedule.realtime_schedule_model import RealtimeScheduleModel
from SimplyTransport.domain.realtime.stop_time.rt_stop_time_model import RTStopTimeModel
from SimplyTransport.domain.realtime.trip.rt_trip_model import RTTripModel
from SimplyTransport.domain.schedule.static_schedule_model import StaticScheduleModel
from SimplyTransport.domain.stop_times.stop_time_model import StopTimeModel


def _static(arrival: str = "12:00:00") -> StaticScheduleModel:
    return StaticScheduleModel(
        stop_time=StopTimeModel(arrival_time=time.fromisoformat(arrival)),
        route=AsyncMock(),
        calendar=AsyncMock(),
        stop=AsyncMock(),
        trip=AsyncMock(),
        is_added_exception=False,
    )


def _rt_stop(
    *,
    delay: int | None = 0,
    rel: ScheduleRelationship = ScheduleRelationship.SCHEDULED,
) -> RTStopTimeModel:
    return cast(
        RTStopTimeModel,
        SimpleNamespace(
            arrival_delay=delay,
            departure_delay=delay,
            schedule_relationship=rel,
        ),
    )


def _rt_trip(rel: ScheduleRelationship) -> RTTripModel:
    return cast(RTTripModel, SimpleNamespace(schedule_relationship=rel))


def test_no_realtime_uses_static_arrival_and_unknown_status():
    model = RealtimeScheduleModel(_static("12:00:00"))
    assert model.delay == "-"
    assert model.delay_in_seconds == 0
    assert model.real_arrival_time == time(12, 0, 0)
    assert model.on_time_status is OnTimeStatus.UNKNOWN
    assert model.is_trip_removed is False


def test_cancelled_trip_ignores_stop_time_and_is_unknown():
    model = RealtimeScheduleModel(
        _static("12:00:00"),
        rt_stop_time=_rt_stop(delay=400),
        rt_trip=_rt_trip(ScheduleRelationship.CANCELED),
    )
    assert model.is_trip_removed is True
    assert model.delay == "Cancelled"
    assert model.delay_in_seconds == 0
    assert model.on_time_status is OnTimeStatus.UNKNOWN


def test_exact_skipped_stop_sets_skipped_status():
    model = RealtimeScheduleModel(
        _static("12:00:00"),
        rt_stop_time=_rt_stop(rel=ScheduleRelationship.SKIPPED),
        rt_stop_overlay_exact=True,
    )
    assert model.delay == "Skipped"
    assert model.on_time_status is OnTimeStatus.SKIPPED


def test_trip_only_update_is_unknown_without_stop_time():
    model = RealtimeScheduleModel(
        _static("12:00:00"),
        rt_trip=_rt_trip(ScheduleRelationship.SCHEDULED),
    )
    assert model.delay == "-"
    assert model.delay_in_seconds == 0
    assert model.on_time_status is OnTimeStatus.UNKNOWN


def test_delay_text_uses_minutes_from_max_delay():
    model = RealtimeScheduleModel(_static("12:00:00"), rt_stop_time=_rt_stop(delay=185))
    assert model.delay_in_seconds == 185
    assert model.delay == "3 min"


def test_negative_delay_keeps_sign_in_minutes():
    model = RealtimeScheduleModel(_static("12:00:00"), rt_stop_time=_rt_stop(delay=-125))
    assert model.delay_in_seconds == -125
    assert model.delay == "-3 min"


@freeze_time("2026-03-21 12:00:00")
def test_eta_less_than_one_minute_is_not_due():
    model = RealtimeScheduleModel(_static("12:00:30"))
    assert model.real_eta_text == "<1 min"
    assert model.is_due is False


@freeze_time("2026-03-21 12:00:30")
def test_eta_due_sets_is_due_in_the_last_minute():
    model = RealtimeScheduleModel(_static("12:00:00"))
    assert model.real_eta_text == "Due"
    assert model.is_due is True


@freeze_time("2026-03-21 12:02:00")
def test_eta_left_when_more_than_a_minute_past():
    model = RealtimeScheduleModel(_static("12:00:00"))
    assert model.real_eta_text == "Left"
    assert model.is_due is False


@freeze_time("2026-03-21 12:00:00")
def test_eta_minutes_until_arrival():
    model = RealtimeScheduleModel(_static("12:07:40"))
    assert model.real_eta_text == "7 min"


@freeze_time("2026-03-21 12:00:00")
def test_on_time_status_thresholds():
    on_time = RealtimeScheduleModel(_static("12:00:00"), rt_stop_time=_rt_stop(delay=300))
    late = RealtimeScheduleModel(_static("12:00:00"), rt_stop_time=_rt_stop(delay=301))
    early = RealtimeScheduleModel(_static("12:00:00"), rt_stop_time=_rt_stop(delay=-61))
    barely_early = RealtimeScheduleModel(_static("12:00:00"), rt_stop_time=_rt_stop(delay=-60))
    assert on_time.on_time_status is OnTimeStatus.ON_TIME
    assert late.on_time_status is OnTimeStatus.LATE
    assert early.on_time_status is OnTimeStatus.EARLY
    assert barely_early.on_time_status is OnTimeStatus.ON_TIME


@freeze_time("2026-03-21 00:10:00")
def test_eta_wraps_when_arrival_is_previous_evening():
    model = RealtimeScheduleModel(_static("23:50:00"))
    assert model.real_eta_text == "Left"


@freeze_time("2026-03-21 23:50:00")
def test_eta_wraps_when_arrival_is_just_after_midnight():
    model = RealtimeScheduleModel(_static("00:10:00"))
    assert model.real_eta_text == "20 min"


@freeze_time("2026-03-21 12:00:00")
def test_on_time_wraps_scheduled_evening_to_real_after_midnight():
    model = RealtimeScheduleModel(_static("23:50:00"), rt_stop_time=_rt_stop(delay=25 * 60))
    assert model.real_arrival_time.hour == 0
    assert model.on_time_status is OnTimeStatus.LATE
