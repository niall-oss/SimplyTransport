from collections.abc import Sequence

from litestar.di import NamedDependency
from sqlalchemy.ext.asyncio import AsyncSession

from ..realtime.enums import REMOVED_TRIP_RELATIONSHIPS, OnTimeStatus
from ..realtime.realtime_schedule.model import RealTimeScheduleModel
from ..realtime.realtime_schedule.repo import RealtimeScheduleRepository
from ..realtime.stop_time.repo import RTStopTimeRepository
from ..realtime.trip.repo import RTTripRepository
from ..realtime.vehicle.repo import RTVehicleRepository
from ..schedule.model import StaticScheduleModel


class RealTimeService:
    def __init__(
        self,
        rt_stop_repository: RTStopTimeRepository,
        rt_trip_repository: RTTripRepository,
        rt_vehicle_repository: RTVehicleRepository,
        realtime_schedule_repository: RealtimeScheduleRepository,
    ):
        self.rt_stop_repository = rt_stop_repository
        self.rt_trip_repository = rt_trip_repository
        self.rt_vehicle_repository = rt_vehicle_repository
        self.realtime_schedule_repository = realtime_schedule_repository

    async def get_realtime_schedules_for_static_schedules(
        self, schedules: Sequence[StaticScheduleModel]
    ) -> list[RealTimeScheduleModel]:
        """Returns a list of RealTimeSchedule objects for the given list of StaticSchedule objects"""

        if not schedules:
            return []

        (
            overlay_trips,
            overlay_stop_times,
        ) = await self.realtime_schedule_repository.load_recent_rt_overlay_for_schedules(schedules)

        realtime_schedules: list[RealTimeScheduleModel] = []
        for static in schedules:
            trip_id = static.trip.id
            rt_trip = overlay_trips.get(trip_id)
            key = (trip_id, static.stop.id, static.stop_time.stop_sequence)
            stop_overlay = overlay_stop_times.get(key)
            rt_stop_time = stop_overlay.row if stop_overlay is not None else None
            overlay_exact = stop_overlay.exact_match if stop_overlay is not None else False

            if rt_trip is not None and rt_trip.schedule_relationship in REMOVED_TRIP_RELATIONSHIPS:
                realtime_schedules.append(
                    RealTimeScheduleModel(static_schedule=static, rt_trip=rt_trip, rt_stop_time=None)
                )
            elif rt_stop_time is not None:
                realtime_schedules.append(
                    RealTimeScheduleModel(
                        static_schedule=static,
                        rt_stop_time=rt_stop_time,
                        rt_trip=rt_trip,
                        rt_stop_overlay_exact=overlay_exact,
                    )
                )
            elif rt_trip is not None:
                realtime_schedules.append(
                    RealTimeScheduleModel(static_schedule=static, rt_trip=rt_trip, rt_stop_time=None)
                )
            else:
                realtime_schedules.append(RealTimeScheduleModel(static_schedule=static))

        return realtime_schedules

    async def apply_custom_23_00_sorting(
        self, realtime_schedules: list[RealTimeScheduleModel]
    ) -> list[RealTimeScheduleModel]:
        """Sorts the realtime schedules by realtime arrival time"""

        def custom_sort_key(realtime_schedule: RealTimeScheduleModel):
            arrival_time = realtime_schedule.real_arrival_time

            # Handle the exception case where times in the range 00:00 to 02:00
            # sort after times in the range 23:00 to 23:59
            if 0 <= arrival_time.hour <= 2:
                return (24, arrival_time.hour, arrival_time.minute, arrival_time.second)
            else:
                return (arrival_time.hour, arrival_time.minute, arrival_time.second)

        sorted_schedules = sorted(realtime_schedules, key=custom_sort_key)

        return sorted_schedules

    def filter_to_only_due_schedules(
        self, realtime_schedules: list[RealTimeScheduleModel]
    ) -> list[RealTimeScheduleModel]:
        """Filters the realtime schedules to only those that are due"""

        due_schedules = [schedule for schedule in realtime_schedules if schedule.is_due]
        return due_schedules

    def filter_to_only_schedules_with_updates(
        self, realtime_schedules: list[RealTimeScheduleModel]
    ) -> list[RealTimeScheduleModel]:
        """Filters the realtime schedules to only those that have realtime updates"""

        realtime_schedules = [
            schedule for schedule in realtime_schedules if schedule.on_time_status != OnTimeStatus.UNKNOWN
        ]
        return realtime_schedules

    async def get_distinct_realtime_trips(self) -> list[str]:
        """Returns all distinct trips."""

        return await self.realtime_schedule_repository.get_distinct_realtime_trips()


async def provide_realtime_service(db_session: NamedDependency[AsyncSession]) -> RealTimeService:
    """Constructs repository and service objects for the realtime service."""

    return RealTimeService(
        rt_stop_repository=RTStopTimeRepository(session=db_session),
        rt_trip_repository=RTTripRepository(session=db_session),
        rt_vehicle_repository=RTVehicleRepository(session=db_session),
        realtime_schedule_repository=RealtimeScheduleRepository(session=db_session),
    )
