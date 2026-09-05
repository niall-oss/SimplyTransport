from datetime import UTC, datetime
from types import SimpleNamespace
from typing import cast

from SimplyTransport.domain.realtime.enums import ScheduleRelationship
from SimplyTransport.domain.realtime.realtime_schedule.realtime_schedule_repo import (
    overlay_for_static_schedule_row,
)
from SimplyTransport.domain.realtime.stop_time.rt_stop_time_model import RTStopTimeModel

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
