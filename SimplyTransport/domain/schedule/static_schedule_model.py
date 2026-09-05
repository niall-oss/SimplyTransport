from datetime import date, time

from ..calendar.calendar_model import CalendarModel
from ..route.route_model import RouteModel
from ..stop.stop_model import StopModel
from ..stop_times.stop_time_model import StopTimeModel
from ..trip.trip_model import TripModel

__all__ = ["StaticScheduleModel"]


class StaticScheduleModel:
    __slots__ = ("route", "stop_time", "calendar", "stop", "trip", "is_added_exception")

    def __init__(
        self,
        route: RouteModel,
        stop_time: StopTimeModel,
        calendar: CalendarModel,
        stop: StopModel,
        trip: TripModel,
        is_added_exception: bool,
    ):
        self.route = route
        self.stop_time = stop_time
        self.calendar = calendar
        self.stop = stop
        self.trip = trip
        self.is_added_exception = is_added_exception

    def is_active_on_date(self, date: date) -> bool:
        return self.calendar.is_active_on_date(date)

    def is_active_between_times(self, date: date, start_time: time, end_time: time) -> bool:
        return self.calendar.is_active_on_date(date) and self.stop_time.is_active_between_times(
            start_time=start_time, end_time=end_time
        )
