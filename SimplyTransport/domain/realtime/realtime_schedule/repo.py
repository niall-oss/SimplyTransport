import datetime
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass

from litestar.di import NamedDependency
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...schedule.model import StaticScheduleModel
from ..enums import ScheduleRealtionship
from ..stop_time.model import RTStopTimeModel
from ..trip.model import RTTripModel


@dataclass(frozen=True, slots=True)
class RTStopTimeOverlay:
    """Realtime stop row chosen for a static schedule cell, and whether it is an exact GTFS match."""

    row: RTStopTimeModel
    exact_match: bool


def _pick_predecessor_carry_forward(
    trip_rows: list[RTStopTimeModel], static_sequence: int
) -> RTStopTimeModel | None:
    predecessors = [r for r in trip_rows if r.stop_sequence <= static_sequence]
    if not predecessors:
        return None
    non_skipped = [r for r in predecessors if r.schedule_relationship != ScheduleRealtionship.SKIPPED]
    if non_skipped:
        return max(non_skipped, key=lambda r: (r.stop_sequence, r.created_at))
    return max(predecessors, key=lambda r: (r.stop_sequence, r.created_at))


def _pick_successor_carry_forward(
    trip_rows: list[RTStopTimeModel], static_sequence: int
) -> RTStopTimeModel | None:
    successors = [r for r in trip_rows if r.stop_sequence >= static_sequence]
    if not successors:
        return None
    non_skipped = [r for r in successors if r.schedule_relationship != ScheduleRealtionship.SKIPPED]
    pool = non_skipped if non_skipped else successors
    min_sq = min(r.stop_sequence for r in pool)
    at_min = [r for r in pool if r.stop_sequence == min_sq]
    return max(at_min, key=lambda r: r.created_at)


def overlay_for_static_schedule_row(
    trip_id: str,
    stop_id: str,
    stop_sequence: int,
    by_triple: dict[tuple[str, str, int], RTStopTimeModel],
    trip_rows: list[RTStopTimeModel],
) -> RTStopTimeOverlay | None:
    """
    Resolve which RT stop-time row applies to one static stop_time row.

    Exact (trip_id, stop_id, stop_sequence) matches are exact_match=True. Otherwise we carry
    delay forward from the latest predecessor (preferring non-SKIPPED rows), then earliest successor.
    """
    key = (trip_id, stop_id, stop_sequence)
    exact = by_triple.get(key)
    if exact is not None:
        return RTStopTimeOverlay(row=exact, exact_match=True)
    row = _pick_predecessor_carry_forward(trip_rows, stop_sequence)
    if row is None:
        row = _pick_successor_carry_forward(trip_rows, stop_sequence)
    if row is None:
        return None
    return RTStopTimeOverlay(row=row, exact_match=False)


class RealtimeScheduleRepository:
    """RealtimeScheduleRepository repository."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def load_recent_rt_overlay_for_schedules(
        self, schedules: Sequence[StaticScheduleModel]
    ) -> tuple[dict[str, RTTripModel], dict[tuple[str, str, int], RTStopTimeOverlay]]:
        """
        Load recent rt_trip rows by trip_id and rt_stop_time overlay keyed by
        (trip_id, stop_id, stop_sequence) for each static schedule row.

        Feeds often omit many stops; we only store updates the producer sent. Match in order:
        exact (trip, stop, sequence); else latest RT row on that trip with stop_sequence <= static
        (delay carried forward, preferring rows that are not SKIPPED); else earliest RT row with
        stop_sequence >= static (again preferring non-SKIPPED at the minimum sequence).

        schedule_relationship SKIPPED is only meaningful for exact matches;
        """
        if not schedules:
            return {}, {}

        dataset = schedules[0].trip.dataset
        trip_ids = list[str](set[str]({s.trip.id for s in schedules}))
        thirty_mins_ago = datetime.datetime.now(datetime.UTC) - datetime.timedelta(minutes=30)

        trips_stmt = select(RTTripModel).where(
            RTTripModel.trip_id.in_(trip_ids),
            RTTripModel.dataset == dataset,
            RTTripModel.created_at >= thirty_mins_ago,
        )
        trips_result = await self.session.execute(trips_stmt)
        trips_by_id: dict[str, RTTripModel] = {}
        for row in trips_result.scalars():
            existing = trips_by_id.get(row.trip_id)
            if existing is None or row.created_at > existing.created_at:
                trips_by_id[row.trip_id] = row

        stop_map: dict[tuple[str, str, int], RTStopTimeOverlay] = {}
        if trip_ids:
            st_stmt = select(RTStopTimeModel).where(
                RTStopTimeModel.dataset == dataset,
                RTStopTimeModel.created_at >= thirty_mins_ago,
                RTStopTimeModel.trip_id.in_(trip_ids),
            )
            st_result = await self.session.execute(st_stmt)
            by_triple: dict[tuple[str, str, int], RTStopTimeModel] = {}
            by_trip: dict[str, list[RTStopTimeModel]] = defaultdict(list)
            for st in st_result.scalars():
                t, s, sq = st.trip_id, st.stop_id, st.stop_sequence
                by_trip[t].append(st)
                k3 = (t, s, sq)
                prev = by_triple.get(k3)
                if prev is None or st.created_at > prev.created_at:
                    by_triple[k3] = st

            for static in schedules:
                trip_id = static.trip.id
                stop_id = static.stop.id
                seq = static.stop_time.stop_sequence
                key = (trip_id, stop_id, seq)
                resolved = overlay_for_static_schedule_row(
                    trip_id, stop_id, seq, by_triple, by_trip.get(trip_id, [])
                )
                if resolved is not None:
                    stop_map[key] = resolved

        return trips_by_id, stop_map

    async def get_distinct_realtime_trips(self) -> list[str]:
        """
        Returns all distinct trips.
        """
        trips_statement = select(RTTripModel.trip_id).distinct()
        result = await self.session.execute(trips_statement)
        return [trip[0] for trip in result]


async def provide_schedule_update_repo(
    db_session: NamedDependency[AsyncSession],
) -> RealtimeScheduleRepository:
    """This provides the RealtimeSchedule repository."""

    return RealtimeScheduleRepository(session=db_session)
