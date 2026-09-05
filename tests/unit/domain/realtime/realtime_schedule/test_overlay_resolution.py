from datetime import UTC, datetime
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock, MagicMock

import pytest
from SimplyTransport.domain.realtime.enums import ScheduleRelationship
from SimplyTransport.domain.realtime.realtime_schedule.realtime_schedule_repo import (
    RealtimeScheduleRepo,
    overlay_for_static_schedule_row,
)
from SimplyTransport.domain.realtime.stop_time.rt_stop_time_model import RTStopTimeModel
from SimplyTransport.domain.schedule.static_schedule_model import StaticScheduleModel

_utc = datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)
_utc_later = datetime(2025, 1, 1, 12, 1, 0, tzinfo=UTC)


def _row(
    stop_id: str,
    stop_sequence: int,
    *,
    rel: ScheduleRelationship = ScheduleRelationship.SCHEDULED,
    created_at: datetime | None = None,
):
    return SimpleNamespace(
        trip_id="T1",
        stop_id=stop_id,
        stop_sequence=stop_sequence,
        schedule_relationship=rel,
        created_at=created_at or _utc,
        arrival_delay=0,
        departure_delay=0,
    )


def test_overlay_exact_match_returns_skipped_row_with_exact_true():
    skipped = _row("S10", 10, rel=ScheduleRelationship.SKIPPED)
    key: tuple[str, str, int] = ("T1", "S10", 10)
    by_triple: dict[tuple[str, str, int], RTStopTimeModel] = {key: cast(RTStopTimeModel, skipped)}
    out = overlay_for_static_schedule_row("T1", "S10", 10, by_triple, cast(list[RTStopTimeModel], [skipped]))
    assert out is not None
    assert out.exact_match is True
    assert out.row is skipped


def test_overlay_predecessor_prefers_non_skipped_over_later_skipped():
    r5 = _row("S5", 5, created_at=_utc)
    r8 = _row("S8", 8, rel=ScheduleRelationship.SKIPPED, created_at=_utc_later)
    by_triple: dict[tuple[str, str, int], RTStopTimeModel] = {}
    trip_rows = cast(list[RTStopTimeModel], [r5, r8])
    out = overlay_for_static_schedule_row("T1", "S10", 10, by_triple, trip_rows)
    assert out is not None
    assert out.exact_match is False
    assert out.row.stop_sequence == 5


def test_overlay_successor_prefers_non_skipped_at_min_sequence():
    r12 = _row("S12", 12, rel=ScheduleRelationship.SCHEDULED, created_at=_utc)
    r15 = _row("S15", 15, rel=ScheduleRelationship.SKIPPED, created_at=_utc_later)
    by_triple: dict[tuple[str, str, int], RTStopTimeModel] = {}
    trip_rows = cast(list[RTStopTimeModel], [r12, r15])
    out = overlay_for_static_schedule_row("T1", "S10", 10, by_triple, trip_rows)
    assert out is not None
    assert out.exact_match is False
    assert out.row.stop_sequence == 12


def test_overlay_falls_through_to_successor_when_no_predecessor():
    later = _row("S20", 20)
    out = overlay_for_static_schedule_row("T1", "S10", 10, {}, cast(list[RTStopTimeModel], [later]))
    assert out is not None
    assert out.exact_match is False
    assert out.row.stop_sequence == 20


def test_overlay_all_skipped_predecessors_still_picks_latest_skipped():
    r3 = _row("S3", 3, rel=ScheduleRelationship.SKIPPED, created_at=_utc)
    r7 = _row("S7", 7, rel=ScheduleRelationship.SKIPPED, created_at=_utc_later)
    out = overlay_for_static_schedule_row("T1", "S10", 10, {}, cast(list[RTStopTimeModel], [r3, r7]))
    assert out is not None
    assert out.row.stop_sequence == 7
    assert out.row.schedule_relationship == ScheduleRelationship.SKIPPED


def test_overlay_empty_trip_rows_returns_none():
    assert overlay_for_static_schedule_row("T1", "S10", 10, {}, []) is None


def test_overlay_same_sequence_predecessor_prefers_newer_created_at():
    older = _row("S8", 8, created_at=_utc)
    newer = _row("S8b", 8, created_at=_utc_later)
    out = overlay_for_static_schedule_row("T1", "S10", 10, {}, cast(list[RTStopTimeModel], [older, newer]))
    assert out is not None
    assert out.row is newer


def _static_schedule() -> StaticScheduleModel:
    stop_time = MagicMock()
    stop_time.stop_sequence = 10
    stop = MagicMock()
    stop.id = "S10"
    trip = MagicMock()
    trip.id = "T1"
    trip.dataset = "TFI"
    return StaticScheduleModel(
        route=MagicMock(),
        stop_time=stop_time,
        calendar=MagicMock(),
        stop=stop,
        trip=trip,
        is_added_exception=False,
    )


def _scalars_result(rows: list) -> MagicMock:
    result = MagicMock()
    result.scalars.return_value = rows
    return result


@pytest.mark.asyncio
async def test_load_recent_returns_empty_for_no_schedules():
    repo = RealtimeScheduleRepo(session=AsyncMock())
    trips, stops = await repo.load_recent_rt_overlay_for_schedules([])
    assert trips == {}
    assert stops == {}


@pytest.mark.asyncio
async def test_load_recent_prefers_newer_created_at_for_same_triple():
    older = _row("S10", 10, created_at=_utc)
    newer = _row("S10", 10, created_at=_utc_later)
    rt_trip_old = SimpleNamespace(trip_id="T1", created_at=_utc)
    rt_trip_new = SimpleNamespace(trip_id="T1", created_at=_utc_later)
    session = AsyncMock()
    session.execute = AsyncMock(
        side_effect=[
            _scalars_result([rt_trip_old, rt_trip_new]),
            _scalars_result([older, newer]),
        ]
    )
    repo = RealtimeScheduleRepo(session=session)
    trips, stops = await repo.load_recent_rt_overlay_for_schedules([_static_schedule()])
    assert trips["T1"] is rt_trip_new
    overlay = stops[("T1", "S10", 10)]
    assert overlay.exact_match is True
    assert overlay.row is newer
