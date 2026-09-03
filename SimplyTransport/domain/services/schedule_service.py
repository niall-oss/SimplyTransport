from datetime import date, time

from litestar.di import NamedDependency
from sqlalchemy.ext.asyncio import AsyncSession

from ..calendar_dates.repo import CalendarDateRepository
from ..enums import DayOfWeek
from ..schedule.model import StaticScheduleModel
from ..schedule.repo import ScheduleRepository


class ScheduleService:
    def __init__(
        self,
        schedule_repository: ScheduleRepository,
        calendar_date_repository: CalendarDateRepository,
    ):
        self.schedule_repository = schedule_repository
        self.calendar_date_respository = calendar_date_repository

    async def get_schedule_on_stop_for_day(self, stop_id: str, day: DayOfWeek) -> list[StaticScheduleModel]:
        """Returns a list of schedules for the given stop and day"""
        return await self.schedule_repository.get_static_schedules(stop_id=stop_id, day=day)

    async def get_all_schedule_for_day_between_times(
        self, day: DayOfWeek, start_time: time, end_time: time, trips: list[str]
    ) -> list[StaticScheduleModel]:
        """Returns all schedules that are currently active"""
        return await self.schedule_repository.get_static_schedules(
            day=day, start_time=start_time, end_time=end_time, trips=trips
        )

    async def get_schedule_on_stop_for_day_between_times(
        self, stop_id: str, day: DayOfWeek, start_time: time, end_time: time
    ) -> list[StaticScheduleModel]:
        """Returns a list of schedules for the given stop and day"""
        return await self.schedule_repository.get_static_schedules(
            stop_id=stop_id, day=day, start_time=start_time, end_time=end_time
        )

    async def apply_custom_23_00_sorting(
        self, static_schedules: list[StaticScheduleModel]
    ) -> list[StaticScheduleModel]:
        """Sorts the schedules by arrival time"""

        def custom_sort_key(static_schedule: StaticScheduleModel) -> tuple[int, ...]:
            arrival_time = static_schedule.stop_time.arrival_time

            # Handle the exception case where times in the range 00:00 to 02:00
            # sort after times in the range 23:00 to 23:59
            if 0 <= arrival_time.hour <= 2:
                return (24, arrival_time.hour, arrival_time.minute, arrival_time.second)
            else:
                return (arrival_time.hour, arrival_time.minute, arrival_time.second)

        sorted_schedules = sorted(static_schedules, key=custom_sort_key)

        return sorted_schedules

    async def remove_exceptions_and_inactive_calendars(
        self, static_schedules: list[StaticScheduleModel]
    ) -> list[StaticScheduleModel]:
        """Removes exceptions from the list of schedules"""
        current_day = date.today()
        exceptions_from_db = await self.calendar_date_respository.get_removed_exceptions_on_date(
            date=current_day
        )
        removed_exception_service_ids = {exc.service_id for exc in exceptions_from_db}

        static_schedules_filtered = []
        for schedule in static_schedules:
            if not schedule.true_if_active(date=current_day):
                continue
            if schedule.calendar.id in removed_exception_service_ids:
                continue
            static_schedules_filtered.append(schedule)

        return static_schedules_filtered

    async def add_in_added_exceptions(
        self, static_schedules: list[StaticScheduleModel]
    ) -> list[StaticScheduleModel]:
        """Adds in added exceptions from the list of schedules"""
        pass  # TODO

        return static_schedules

    async def get_by_trip_id(self, trip_id: str) -> list[StaticScheduleModel]:
        """Returns a list of schedules for the given trip_id"""
        return await self.schedule_repository.get_by_trip_id(trip_id=trip_id)


async def provide_schedule_service(db_session: NamedDependency[AsyncSession]) -> ScheduleService:
    """Constructs repository and service objects for the schedule service."""
    return ScheduleService(ScheduleRepository(session=db_session), CalendarDateRepository(session=db_session))
