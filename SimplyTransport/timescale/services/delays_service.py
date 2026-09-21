from datetime import date, datetime, time, timedelta

from SimplyTransport.domain.realtime.enums import REMOVED_TRIP_RELATIONSHIPS, ScheduleRelationship
from SimplyTransport.domain.realtime.realtime_schedule.realtime_schedule_model import (
    is_due_arrival,
    real_arrival_time,
)
from SimplyTransport.domain.realtime.realtime_schedule.realtime_schedule_repo import RTStopTimeOverlay
from SimplyTransport.domain.realtime.trip.rt_trip_model import RTTripModel
from SimplyTransport.domain.schedule.static_schedule_model import StaticScheduleModel
from SimplyTransport.domain.services.realtime_service import RealtimeService, provide_realtime_service
from SimplyTransport.lib.cache import RedisService
from SimplyTransport.lib.cache_keys import CacheKeys
from SimplyTransport.lib.constants import CLEANUP_DELAYS_AFTER_DAYS
from SimplyTransport.lib.logging.logging import provide_logger
from SimplyTransport.lib.tracing import CreateSpan, get_app_tracer
from SimplyTransport.timescale.ts_stop_times.ts_stop_time_model import TSStopTimeModel
from sqlalchemy.ext.asyncio import AsyncSession

from ...domain.enums import DayOfWeek
from ...domain.services.schedule_service import ScheduleService, provide_schedule_service
from ..ts_stop_times.ts_stop_time_repo import TSStopTimeRepo

logger = provide_logger(__name__)


def delay_recording_cache_key(route_code: str, stop_id: str, scheduled_time: time) -> str:
    return CacheKeys.Delays.DELAYS_RECORDING_KEY_TEMPLATE.format(
        route_code=route_code,
        stop_id=stop_id,
        scheduled_time=scheduled_time,
    )


def due_delay_records(
    schedules: list[StaticScheduleModel],
    overlay_trips: dict[str, RTTripModel],
    overlay_stop_times: dict[tuple[str, str, int], RTStopTimeOverlay],
    *,
    now: datetime | None = None,
) -> list[TSStopTimeModel]:
    """Timescale rows for overlayed stops whose real arrival is in the Due window."""
    now = now or datetime.now()
    records: list[TSStopTimeModel] = []
    for static in schedules:
        trip_id = static.trip.id
        rt_trip = overlay_trips.get(trip_id)
        if rt_trip is not None and rt_trip.schedule_relationship in REMOVED_TRIP_RELATIONSHIPS:
            continue

        overlay = overlay_stop_times.get((trip_id, static.stop.id, static.stop_time.stop_sequence))
        if overlay is None:
            continue
        if overlay.exact_match and overlay.row.schedule_relationship == ScheduleRelationship.SKIPPED:
            continue

        delay_in_seconds = max(overlay.row.arrival_delay or 0, overlay.row.departure_delay or 0)
        arrival = real_arrival_time(static.stop_time.arrival_time, delay_in_seconds, now)
        if not is_due_arrival(arrival, now):
            continue

        records.append(
            TSStopTimeModel(
                stop_id=static.stop.id,
                route_code=static.route.short_name,
                scheduled_time=static.stop_time.arrival_time,
                delay_in_seconds=delay_in_seconds,
            )
        )
    return records


class DelaysService:
    def __init__(
        self,
        ts_stop_time_repo: TSStopTimeRepo,
        schedule_service: ScheduleService,
        realtime_service: RealtimeService,
        redis_cache: RedisService,
    ):
        self.ts_stop_time_repo = ts_stop_time_repo
        self.schedule_service = schedule_service
        self.realtime_service = realtime_service
        self.redis_cache = redis_cache

    @CreateSpan()
    async def record_all_delays(self) -> int:
        """
        Records all delays for the current day within a specific time range.
        Returns:
            int: The number of delays recorded.
        """

        current_day = DayOfWeek(datetime.now().weekday())
        start_time = datetime.now() - timedelta(minutes=20)
        end_time = datetime.now() + timedelta(minutes=20)
        realtime_trip_ids = await self.realtime_service.get_distinct_realtime_trips()
        logger.info(
            f"Fetching schedules for {current_day} between {start_time} and {end_time} "
            f"using {len(realtime_trip_ids)} trips."
        )

        schedules = await self.schedule_service.get_all_schedule_for_day_between_times(
            day=current_day, start_time=start_time.time(), end_time=end_time.time(), trips=realtime_trip_ids
        )
        logger.info(f"Found {len(schedules)} schedules.")

        on_date = date.today()
        schedules = await self.schedule_service.remove_exceptions_and_inactive_calendars(
            schedules, on_date=on_date
        )
        logger.info(f"Removed exceptions and inactive calendars. {len(schedules)} schedules remaining.")
        schedules = await self.schedule_service.add_in_added_exceptions(
            schedules,
            on_date=on_date,
            start_time=start_time.time(),
            end_time=end_time.time(),
            trips=realtime_trip_ids,
        )

        overlay_trips, overlay_stop_times = await self.realtime_service.load_recent_rt_overlay_for_schedules(
            schedules
        )

        with get_app_tracer().start_as_current_span("DelaysService.build_records"):
            objects_to_commit = due_delay_records(schedules, overlay_trips, overlay_stop_times)

        keys_to_check = [
            delay_recording_cache_key(row.route_code, row.stop_id, row.scheduled_time)
            for row in objects_to_commit
        ]
        keys_in_cache = await self.redis_cache.check_keys_exist(keys_to_check)

        filtered: list[TSStopTimeModel] = []
        keys_to_set: list[str] = []
        for row, key in zip(objects_to_commit, keys_to_check, strict=True):
            if keys_in_cache.get(key, False):
                continue
            filtered.append(row)
            keys_to_set.append(key)

        await self.ts_stop_time_repo.bulk_insert_delay_records(filtered, auto_commit=True)
        await self.redis_cache.set_many_empty_keys(keys_to_set, expiration=60 * 5)
        number_of_delays_recorded = len(keys_to_set)

        logger.info(f"Recorded {number_of_delays_recorded} delays.")
        return number_of_delays_recorded

    async def cleanup_old_delays(self) -> int:
        """
        Cleans up the old delays from the database.
        Returns:
            int: The number of delays deleted.
        """
        cutoff_time = datetime.now() - timedelta(days=CLEANUP_DELAYS_AFTER_DAYS)
        number_of_delays_deleted = await self.ts_stop_time_repo.delete_old_delays(cutoff_time)

        logger.info(f"Deleted {number_of_delays_deleted} delays older than {CLEANUP_DELAYS_AFTER_DAYS} days.")
        return number_of_delays_deleted


async def provide_delays_service(
    timescale_db_session: AsyncSession, db_session: AsyncSession, redis_cache: RedisService
) -> DelaysService:
    """
    Provides a delays service instance.

    Args:
        timescale_db_session (AsyncSession): The timescale database session.
        db_session (AsyncSession): The database session.

    Returns:
        DelaysService: The delays service instance.
    """
    return DelaysService(
        ts_stop_time_repo=TSStopTimeRepo(session=timescale_db_session),
        schedule_service=await provide_schedule_service(db_session=db_session),
        realtime_service=await provide_realtime_service(db_session=db_session),
        redis_cache=redis_cache,
    )
