from datetime import datetime, timedelta

from advanced_alchemy.exceptions import NotFoundError
from litestar import Controller, get
from litestar.di import NamedDependency, Provide
from litestar.params import FromPath, FromQuery
from litestar.response import Template

from SimplyTransport.lib.cache_keys import (
    CacheKeys,
    key_builder_from_path,
    key_builder_from_path_and_query,
)

from ..domain.enums import DayOfWeek, Direction
from ..domain.route.repo import RouteRepository, provide_route_repo
from ..domain.services.realtime_service import (
    RealTimeService,
    provide_realtime_service,
)
from ..domain.services.schedule_service import (
    ScheduleService,
    provide_schedule_service,
)
from ..domain.stop.repo import StopRepository, provide_stop_repo

__all__ = [
    "RealtimeController",
]


class RealtimeController(Controller):
    dependencies = {
        "stop_repo": Provide(provide_stop_repo),
        "route_repo": Provide(provide_route_repo),
        "schedule_service": Provide(provide_schedule_service),
        "realtime_service": Provide(provide_realtime_service),
    }

    @get(
        "/stop/{stop_id:str}",
        cache=120,
        cache_key_builder=key_builder_from_path_and_query(
            CacheKeys.RealTime.REALTIME_STOP_KEY_TEMPLATE, ["stop_id"]
        ),
    )
    async def realtime_stop(
        self,
        stop_id: FromPath[str],
        stop_repo: NamedDependency[StopRepository],
        route_repo: NamedDependency[RouteRepository],
    ) -> Template:
        try:
            stop = await stop_repo.get_by_id_with_stop_feature(stop_id)
        except NotFoundError:
            return Template(
                template_name="/errors/404.html",
                context={"message": "Sorry this stop could not be found, try the search bar above."},
            )
        routes = await route_repo.get_routes_by_stop_id(stop.id)
        routes.sort(key=lambda x: x.short_name)

        current_time = datetime.now()
        return Template(
            template_name="realtime/stop.html",
            context={
                "stop": stop,
                "routes": routes,
                "day_string": DayOfWeek(current_time.weekday()).name.capitalize(),
                "day_int": current_time.weekday(),
            },
        )

    @get(
        "/stop/{stop_id:str}/realtime-table",
        cache=120,
        cache_key_builder=key_builder_from_path(
            CacheKeys.RealTime.REALTIME_STOP_TABLE_KEY_TEMPLATE, "stop_id"
        ),
    )
    async def realtime_stop_table(
        self,
        stop_id: FromPath[str],
        stop_repo: NamedDependency[StopRepository],
        schedule_service: NamedDependency[ScheduleService],
        realtime_service: NamedDependency[RealTimeService],
    ) -> Template:
        try:
            await stop_repo.get_by_id_with_stop_feature(stop_id)
        except NotFoundError:
            return Template(template_name="realtime/stop_realtime_table_not_found_partial.html")

        current_time = datetime.now()
        start_time_difference = -10
        end_time_difference = 60
        start_time = (current_time + timedelta(minutes=start_time_difference)).time()
        end_time = (current_time + timedelta(minutes=end_time_difference)).time()

        schedules = await schedule_service.get_schedule_on_stop_for_day_between_times(
            stop_id=stop_id,
            day=DayOfWeek(datetime.now().weekday()),
            start_time=start_time,
            end_time=end_time,
        )
        schedules = await schedule_service.remove_exceptions_and_inactive_calendars(schedules)
        schedules = await schedule_service.add_in_added_exceptions(schedules)  # TODO
        schedules = await schedule_service.apply_custom_23_00_sorting(schedules)

        realtime_schedules = await realtime_service.get_realtime_schedules_for_static_schedules(schedules)
        realtime_schedules = await realtime_service.apply_custom_23_00_sorting(realtime_schedules)

        return Template(
            template_name="realtime/stop_realtime_table_partial.html",
            context={
                "stop_id": stop_id,
                "current_time": current_time,
                "realtime_schedules": realtime_schedules,
                "start_time_difference": start_time_difference,
                "end_time_difference": end_time_difference,
            },
        )

    @get(
        "/stop/{stop_id:str}/schedule",
        cache=86400,
        cache_key_builder=key_builder_from_path_and_query(
            CacheKeys.Schedules.SCHEDULE_KEY_TEMPLATE, ["stop_id"], ["day"]
        ),
    )
    async def realtime_stop_schedule(
        self,
        stop_id: FromPath[str],
        schedule_service: NamedDependency[ScheduleService],
        day: FromQuery[DayOfWeek | None] = None,
    ) -> Template:
        if day is None:
            day = DayOfWeek(datetime.now().weekday())
        schedules = await schedule_service.get_schedule_on_stop_for_day(stop_id=stop_id, day=day)
        schedules = await schedule_service.remove_exceptions_and_inactive_calendars(schedules)
        schedules = await schedule_service.add_in_added_exceptions(schedules)  # TODO

        return Template(
            template_name="realtime/stop_schedule.html",
            context={
                "schedules": schedules,
                "day_string": DayOfWeek(day).name.capitalize(),
            },
        )

    @get(
        "/route/{route_id:str}/{direction:int}",
        cache=86400,
        cache_key_builder=key_builder_from_path(
            CacheKeys.RealTime.REALTIME_ROUTE_KEY_TEMPLATE, "route_id", "direction"
        ),
    )
    async def realtime_route(
        self,
        route_id: FromPath[str],
        direction: FromPath[Direction],
        route_repo: NamedDependency[RouteRepository],
        stop_repo: NamedDependency[StopRepository],
    ) -> Template:
        try:
            route = await route_repo.get_by_id_with_agency(route_id)
        except NotFoundError:
            return Template(
                template_name="/errors/404.html",
                context={"message": "Sorry this route could not be found, try the search bar above."},
            )
        stops_and_sequences = await stop_repo.get_by_route_id_with_sequence(route.id, direction)

        return Template(
            template_name="realtime/route.html",
            context={"route": route, "stops": stops_and_sequences, "direction": direction},
        )

    @get(
        "/trip/{trip_id:str}",
        cache=20,
        cache_key_builder=key_builder_from_path_and_query(
            CacheKeys.RealTime.REALTIME_TRIP_KEY_TEMPLATE, ["trip_id"]
        ),
    )
    async def realtime_trip(
        self,
        trip_id: FromPath[str],
        schedule_service: NamedDependency[ScheduleService],
        realtime_service: NamedDependency[RealTimeService],
    ) -> Template:
        schedules = await schedule_service.get_by_trip_id(trip_id=trip_id)

        if len(schedules) == 0:
            return Template(
                template_name="/errors/404.html", context={"message": "Schedule for trip not found"}
            )

        schedules = await schedule_service.apply_custom_23_00_sorting(schedules)

        realtime_schedules = await realtime_service.get_realtime_schedules_for_static_schedules(schedules)
        realtime_schedules = await realtime_service.apply_custom_23_00_sorting(realtime_schedules)

        prime_schedule = realtime_schedules[0].static_schedule
        direction_value = prime_schedule.trip.direction
        direction_string = "Southbound" if direction_value == 0 else "Northbound"

        return Template(
            template_name="realtime/trip.html",
            context={
                "rt_schedules": realtime_schedules,
                "direction_string": direction_string,
                "prime_schedule": prime_schedule,
            },
        )
