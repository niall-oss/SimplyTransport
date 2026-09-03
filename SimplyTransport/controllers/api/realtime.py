from datetime import datetime, timedelta

from litestar import Controller, get
from litestar.di import NamedDependency, Provide
from litestar.exceptions import ValidationException
from litestar.params import FromPath

from SimplyTransport.api_contract.realtime_schedule import RealTimeSchedule

from ...domain.enums import DayOfWeek
from ...domain.services.realtime_service import (
    RealTimeService,
    provide_realtime_service,
)
from ...domain.services.schedule_service import (
    ScheduleService,
    provide_schedule_service,
)
from ...lib.parameters.time_query import DayQuery, EndTimeQuery, StartTimeQuery
from ...lib.time_date_conversions import next_date_for_day, return_time_difference

__all__ = ["RealtimeController"]


class RealtimeController(Controller):
    dependencies = {
        "schedule_service": Provide(provide_schedule_service),
        "realtime_service": Provide(provide_realtime_service),
    }

    @get("/{stop_id:str}", summary="Get realtime schedule for a stop", raises=[ValidationException])
    async def get_realtime_schedule_by_stop_id(
        self,
        schedule_service: NamedDependency[ScheduleService],
        realtime_service: NamedDependency[RealTimeService],
        stop_id: FromPath[str],
        start_time: StartTimeQuery = None,
        end_time: EndTimeQuery = None,
        day: DayQuery = None,
    ) -> list[RealTimeSchedule]:
        """Returns a list of realtime schedules for the given stop_id"""

        if start_time is None:
            start_time = (datetime.now() - timedelta(minutes=10)).time()

        if end_time is None:
            end_time = (datetime.now() + timedelta(minutes=60)).time()

        if day is None:
            day = DayOfWeek(datetime.now().weekday())

        if start_time == end_time:
            raise ValidationException("Start time cannot be equal to end time")

        max_hours_apart = 4
        difference = return_time_difference(start_time, end_time)
        if difference > max_hours_apart:
            raise ValidationException(
                f"The difference of hours between start and end time must be at most {max_hours_apart} hours",
                extra={"start_time": start_time, "end_time": end_time, "hours_difference": difference},
            )

        on_date = next_date_for_day(day)
        schedules = await schedule_service.get_schedule_on_stop_for_day_between_times(
            stop_id=stop_id,
            day=day,
            start_time=start_time,
            end_time=end_time,
        )
        schedules = await schedule_service.remove_exceptions_and_inactive_calendars(
            schedules, on_date=on_date
        )
        schedules = await schedule_service.add_in_added_exceptions(
            schedules,
            on_date=on_date,
            stop_id=stop_id,
            start_time=start_time,
            end_time=end_time,
        )
        schedules = await schedule_service.apply_custom_23_00_sorting(schedules)

        realtime_schedules = await realtime_service.get_realtime_schedules_for_static_schedules(schedules)
        realtime_schedules = await realtime_service.apply_custom_23_00_sorting(realtime_schedules)

        return [RealTimeSchedule.model_validate(realtime) for realtime in realtime_schedules]
