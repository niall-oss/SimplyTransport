from datetime import time
from typing import Any

from litestar.di import NamedDependency
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..calendar.model import CalendarModel
from ..enums import DayOfWeek
from ..route.model import RouteModel
from ..stop.model import StopModel
from ..stop_times.model import StopTimeModel
from ..trip.model import TripModel
from .model import StaticScheduleModel


def _static_schedule_from_row(row: Any) -> StaticScheduleModel:
    stop_time, route, calendar, stop, trip = row
    return StaticScheduleModel(
        route=route,
        stop_time=stop_time,
        calendar=calendar,
        stop=stop,
        trip=trip,
    )


class ScheduleRepository:
    """ScheduleRepository repository."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_static_schedules(
        self,
        day: DayOfWeek,
        stop_id: str | None = None,
        start_time: time | None = None,
        end_time: time | None = None,
        trips: list[str] | None = None,
    ) -> list[StaticScheduleModel]:
        """
        Retrieve static schedules based on the given parameters.
        Parameters:
        - stop_id (str | None): The ID of the stop.
        If provided, only schedules for this stop will be retrieved.
        - day (DayOfWeek): The day of the week for which schedules should be retrieved.
        - start_time (time | None): The start time of the schedules.
        If provided, only schedules with arrival times greater than or equal to this time will be retrieved.
        - end_time (time | None): The end time of the schedules.
        If provided, only schedules with arrival times less than or equal to this time will be retrieved.
        Returns:
        - list[StaticScheduleModel]: The retrieved schedules.
        Raises:
        - ValueError: If an invalid day of the week is provided.
        """

        conditions = []
        if day == DayOfWeek.MONDAY:
            conditions.append(CalendarModel.monday == 1)
        elif day == DayOfWeek.TUESDAY:
            conditions.append(CalendarModel.tuesday == 1)
        elif day == DayOfWeek.WEDNESDAY:
            conditions.append(CalendarModel.wednesday == 1)
        elif day == DayOfWeek.THURSDAY:
            conditions.append(CalendarModel.thursday == 1)
        elif day == DayOfWeek.FRIDAY:
            conditions.append(CalendarModel.friday == 1)
        elif day == DayOfWeek.SATURDAY:
            conditions.append(CalendarModel.saturday == 1)
        elif day == DayOfWeek.SUNDAY:
            conditions.append(CalendarModel.sunday == 1)
        else:
            raise ValueError(f"Invalid day of week {day}")

        if stop_id:
            conditions.append(StopModel.id == stop_id)

        if trips:
            conditions.append(TripModel.id.in_(trips))

        if start_time and end_time:
            if start_time > end_time:
                conditions.append(
                    or_(
                        StopTimeModel.arrival_time >= start_time,
                        StopTimeModel.arrival_time <= end_time,
                    )
                )
            else:
                conditions.append(StopTimeModel.arrival_time >= start_time)
                conditions.append(StopTimeModel.arrival_time <= end_time)

        statement = (
            select(StopTimeModel, RouteModel, CalendarModel, StopModel, TripModel)
            .join(TripModel, TripModel.id == StopTimeModel.trip_id)
            .join(StopModel, StopModel.id == StopTimeModel.stop_id)
            .join(RouteModel, RouteModel.id == TripModel.route_id)
            .join(CalendarModel, CalendarModel.id == TripModel.service_id)
            .where(
                *conditions,
            )
            .order_by(StopTimeModel.arrival_time)
        )

        result = await self.session.execute(statement)
        return [_static_schedule_from_row(row) for row in result]

    async def get_by_trip_id(self, trip_id: str) -> list[StaticScheduleModel]:
        """Returns a list of schedules for the given trip"""
        statement = (
            select(StopTimeModel, RouteModel, CalendarModel, StopModel, TripModel)
            .join(TripModel, TripModel.id == StopTimeModel.trip_id)
            .join(StopModel, StopModel.id == StopTimeModel.stop_id)
            .join(RouteModel, RouteModel.id == TripModel.route_id)
            .join(CalendarModel, CalendarModel.id == TripModel.service_id)
            .where(TripModel.id == trip_id)
            .order_by(StopTimeModel.arrival_time)
        )
        result = await self.session.execute(statement)
        return [_static_schedule_from_row(row) for row in result]


async def provide_schedule_repo(db_session: NamedDependency[AsyncSession]) -> ScheduleRepository:
    """This provides the Schedule repository."""

    return ScheduleRepository(session=db_session)
