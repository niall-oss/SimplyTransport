import asyncio
from collections.abc import Sequence
from datetime import date, datetime, timedelta

import rich.progress as rp
from SimplyTransport.domain.realtime.realtime_schedule.realtime_schedule_model import RealtimeScheduleModel
from SimplyTransport.domain.schedule.static_schedule_model import StaticScheduleModel
from SimplyTransport.domain.services.realtime_service import RealtimeService, provide_realtime_service
from SimplyTransport.lib.cache import RedisService
from SimplyTransport.lib.cache_keys import CacheKeys
from SimplyTransport.lib.constants import CLEANUP_DELAYS_AFTER_DAYS
from SimplyTransport.lib.extensions.chunking import chunk_list
from SimplyTransport.lib.logging.logging import provide_logger
from SimplyTransport.lib.tracing import CreateSpan
from SimplyTransport.timescale.ts_stop_times.ts_stop_time_model import TSStopTimeModel
from sqlalchemy.ext.asyncio import AsyncSession

from ...domain.enums import DayOfWeek
from ...domain.services.schedule_service import ScheduleService, provide_schedule_service
from ..ts_stop_times.ts_stop_time_repo import TSStopTimeRepo

logger = provide_logger(__name__)


progress_columns = (
    rp.SpinnerColumn(finished_text="✅"),
    "[progress.description]{task.description}",
    rp.BarColumn(),
    rp.MofNCompleteColumn(),
    rp.TaskProgressColumn(),
    "|| Taken:",
    rp.TimeElapsedColumn(),
    "|| Left:",
    rp.TimeRemainingColumn(),
)


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

        async def gather_realtime_schedules(
            schedules: Sequence[StaticScheduleModel],
        ) -> list[RealtimeScheduleModel]:
            semaphore = asyncio.Semaphore(4)

            async def limited_task(task):
                async with semaphore:
                    result = await task
                    return result

            tasks = [
                limited_task(
                    self.realtime_service.get_realtime_schedules_for_static_schedules(schedule_batch)
                )
                for schedule_batch in chunk_list(schedules, 2000)
            ]

            with rp.Progress(*progress_columns) as progress:
                progress_task = progress.add_task(
                    "[green]Populating realtime schedules...", total=len(schedules)
                )
                results: list[RealtimeScheduleModel] = []
                for task in asyncio.as_completed(tasks):
                    result = await task
                    results.extend(result)
                    progress.update(progress_task, advance=len(result))

            return results

        realtime_schedules = await gather_realtime_schedules(schedules)
        realtime_schedules = self.realtime_service.filter_to_only_due_schedules(realtime_schedules)
        realtime_schedules = self.realtime_service.filter_to_only_schedules_with_updates(realtime_schedules)

        keys_to_check = [self.create_cache_key_for_schedule(schedule) for schedule in realtime_schedules]
        keys_in_cache = await self.redis_cache.check_keys_exist(keys_to_check)

        objects_to_commit = []
        keys_to_set = []

        for schedule in realtime_schedules:
            key = self.create_cache_key_for_schedule(schedule)
            key_exists = keys_in_cache.get(key, False)

            if key_exists:
                continue

            ts_stop_time = TSStopTimeModel(
                stop_id=schedule.static_schedule.stop.id,
                route_code=schedule.static_schedule.route.short_name,
                scheduled_time=schedule.static_schedule.stop_time.arrival_time,
                delay_in_seconds=schedule.delay_in_seconds,
            )
            keys_to_set.append(key)
            objects_to_commit.append(ts_stop_time)

        await self.ts_stop_time_repo.bulk_insert_delay_records(objects_to_commit, auto_commit=True)
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

    def create_cache_key_for_schedule(self, schedule: RealtimeScheduleModel) -> str:
        return CacheKeys.Delays.DELAYS_RECORDING_KEY_TEMPLATE.format(
            route_code=schedule.static_schedule.route.short_name,
            stop_id=schedule.static_schedule.stop.id,
            scheduled_time=schedule.static_schedule.stop_time.arrival_time,
        )


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
