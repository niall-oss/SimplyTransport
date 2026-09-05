"""Shift E2E / fixture schedules to wall-clock ``now`` for local realtime UI testing."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from SimplyTransport.domain.stop_times.stop_time_model import StopTimeModel
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..domain.calendar.calendar_model import CalendarModel
from ..domain.calendar_dates.calendar_date_model import CalendarDateModel
from ..domain.enums import DayOfWeek, ExceptionType
from ..domain.trip.trip_model import TripModel
from .gtfs_realtime_importers import _effective_trip_id_for_trip_update
from .logging.logging import provide_logger

logger = provide_logger(__name__)

_WEEKDAY_TO_CALENDAR_COL = {
    DayOfWeek.MONDAY: CalendarModel.monday,
    DayOfWeek.TUESDAY: CalendarModel.tuesday,
    DayOfWeek.WEDNESDAY: CalendarModel.wednesday,
    DayOfWeek.THURSDAY: CalendarModel.thursday,
    DayOfWeek.FRIDAY: CalendarModel.friday,
    DayOfWeek.SATURDAY: CalendarModel.saturday,
    DayOfWeek.SUNDAY: CalendarModel.sunday,
}


async def _service_id_active_on_local_today(session: AsyncSession, dataset: str) -> str | None:
    """Pick any calendar in ``dataset`` that runs today (weekday bit, date range, not removed)."""
    today = date.today()
    weekday_col = _WEEKDAY_TO_CALENDAR_COL[DayOfWeek(today.weekday())]
    removed_services = select(CalendarDateModel.service_id).where(
        CalendarDateModel.dataset == dataset,
        CalendarDateModel.date == today,
        CalendarDateModel.exception_type == ExceptionType.removed,
    )
    result = await session.execute(
        select(CalendarModel.id)
        .where(
            CalendarModel.dataset == dataset,
            CalendarModel.start_date <= today,
            CalendarModel.end_date >= today,
            weekday_col == 1,
            CalendarModel.id.not_in(removed_services),
        )
        .limit(1)
    )
    row = result.scalar_one_or_none()
    return str(row) if row else None


async def shift_db_stop_times_and_patch_payload_for_now(
    session: AsyncSession,
    dataset: str,
    payload: dict,
) -> str | None:
    """
    For each distinct ``trip_id`` in the GTFS-RT payload (in first-seen order):

    - Pick an anchor datetime (``now + 2 minutes``, rounded to the minute, plus 10 minutes
      per trip index) and move **all** static ``stop_time`` rows for that trip by the same
      delta so inter-stop spacing is preserved.
    - Patch ``trip`` / ``trip_properties`` ``start_date`` and ``start_time`` in the payload
      to match that anchor.

    CI and pipelines should **not** use this; keep the JSON and GTFS files deterministic.

    Returns the ``service_id`` trips were repointed to for today's weekday, if any; fixtures
    often use weekday-only calendars (e.g. Mon--Fri), which would otherwise yield no rows
    when testing on Saturday/Sunday even after shifting times.
    """
    entities = [e for e in payload.get("entity", []) if e.get("trip_update")]
    trip_order: list[str] = []
    seen: set[str] = set[str]()
    for e in entities:
        tid = _effective_trip_id_for_trip_update(e["trip_update"])
        if tid and tid not in seen:
            seen.add(tid)
            trip_order.append(tid)

    if not trip_order:
        return None

    service_for_today = await _service_id_active_on_local_today(session, dataset)
    if service_for_today is None:
        logger.warning(
            "set-time-to-now: no calendar row for dataset %s is active on local today's weekday; "
            "trips may still be missing from /realtime/stop on weekends.",
            dataset,
        )
    else:
        await session.execute(
            update(TripModel)
            .where(TripModel.dataset == dataset, TripModel.id.in_(trip_order))
            .values(service_id=service_for_today)
        )

    base = (datetime.now() + timedelta(minutes=2)).replace(second=0, microsecond=0)
    trip_anchor: dict[str, datetime] = {
        tid: base + timedelta(minutes=10 * i) for i, tid in enumerate(trip_order)
    }

    today = date.today()
    for tid in trip_order:
        anchor = trip_anchor[tid]
        result = await session.execute(
            select(StopTimeModel)
            .where(StopTimeModel.trip_id == tid, StopTimeModel.dataset == dataset)
            .order_by(StopTimeModel.stop_sequence)
        )
        st_list = list[StopTimeModel](result.scalars().all())
        if not st_list:
            continue
        old_first = datetime.combine(today, st_list[0].arrival_time)
        delta = anchor - old_first
        for st in st_list:
            naive = datetime.combine(today, st.arrival_time) + delta
            st.arrival_time = naive.time()
            st.departure_time = naive.time()

    await session.commit()

    for e in entities:
        tu = e["trip_update"]
        tid = _effective_trip_id_for_trip_update(tu)
        if not tid or tid not in trip_anchor:
            continue
        anchor = trip_anchor[tid]
        trip = tu.setdefault("trip", {})
        trip["start_date"] = anchor.strftime("%Y%m%d")
        trip["start_time"] = anchor.strftime("%H:%M:%S")
        props = tu.get("trip_properties")
        if isinstance(props, dict):
            props["start_date"] = anchor.strftime("%Y%m%d")
            props["start_time"] = anchor.strftime("%H:%M:%S")

    return service_for_today
