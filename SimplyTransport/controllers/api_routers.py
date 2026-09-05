from litestar import Router
from SimplyTransport.controllers.api.agency_controller import AgencyController
from SimplyTransport.controllers.api.calendar_controller import CalendarController
from SimplyTransport.controllers.api.calendar_date_controller import CalendarDateController
from SimplyTransport.controllers.api.delays_controller import DelaysController as DelaysApiController
from SimplyTransport.controllers.api.events_controller import EventsController as EventsApiController
from SimplyTransport.controllers.api.map_controller import MapController
from SimplyTransport.controllers.api.realtime_controller import RealtimeController as RealtimeApiController
from SimplyTransport.controllers.api.route_controller import RouteController
from SimplyTransport.controllers.api.schedule_controller import ScheduleController
from SimplyTransport.controllers.api.shape_controller import ShapeController
from SimplyTransport.controllers.api.statistics_controller import StatisticsController
from SimplyTransport.controllers.api.stop_controller import StopController
from SimplyTransport.controllers.api.stop_time_controller import StopTimeController
from SimplyTransport.controllers.api.trip_controller import TripController
from SimplyTransport.controllers.delays_controller import DelaysController
from SimplyTransport.controllers.events_controller import EventsController
from SimplyTransport.controllers.maps_controller import MapsController
from SimplyTransport.controllers.realtime_controller import RealtimeController
from SimplyTransport.controllers.root_controller import RootController
from SimplyTransport.controllers.search_controller import SearchController
from SimplyTransport.controllers.stats_controller import StatsController
from SimplyTransport.lib.openapi.tags import Tags

__all__ = ["create_api_router", "create_views_router"]


def create_views_router() -> Router:
    root_route_handler = Router(path="/", route_handlers=[RootController], include_in_schema=False)

    search_route_handler = Router(
        path="/search",
        route_handlers=[SearchController],
        include_in_schema=False,
    )

    realtime_route_handler = Router(
        path="/realtime",
        route_handlers=[RealtimeController],
        include_in_schema=False,
    )

    events_route_handler = Router(
        path="/events",
        route_handlers=[EventsController],
        include_in_schema=False,
    )

    maps_route_handler = Router(
        path="/maps",
        route_handlers=[MapsController],
        include_in_schema=False,
    )

    delays_route_handler = Router(
        path="/delays",
        route_handlers=[DelaysController],
        include_in_schema=False,
    )

    static_route_handler = Router(
        path="/stats",
        route_handlers=[StatsController],
        include_in_schema=False,
    )

    return Router(
        path="/",
        route_handlers=[
            root_route_handler,
            search_route_handler,
            realtime_route_handler,
            events_route_handler,
            maps_route_handler,
            delays_route_handler,
            static_route_handler,
        ],
    )


def create_api_router() -> Router:
    tags = Tags()

    agency_route_handler = Router(path="/agency", tags=[tags.AGENCY.name], route_handlers=[AgencyController])
    calendar_route_handler = Router(
        path="/calendar",
        tags=[tags.CALENDAR.name],
        route_handlers=[CalendarController],
    )
    calendar_date_route_handler = Router(
        path="/calendardate",
        tags=[tags.CALENDAR_DATE.name],
        route_handlers=[CalendarDateController],
    )

    route_route_handler = Router(path="/route", tags=[tags.ROUTE.name], route_handlers=[RouteController])

    trip_route_handler = Router(path="/trip", tags=[tags.TRIP.name], route_handlers=[TripController])

    stop_route_handler = Router(path="/stop", tags=[tags.STOP.name], route_handlers=[StopController])

    shape_route_handler = Router(path="/shape", tags=[tags.SHAPE.name], route_handlers=[ShapeController])

    stop_time_handler = Router(
        path="/stoptime",
        tags=[tags.STOP_TIME.name],
        route_handlers=[StopTimeController],
    )
    realtime_route_handler = Router(
        path="/realtime",
        tags=[tags.REALTIME.name],
        route_handlers=[RealtimeApiController],
    )

    schedule_route_handler = Router(
        path="/schedule",
        tags=[tags.SCHEDULE.name],
        route_handlers=[ScheduleController],
    )

    maps_route_handler = Router(path="/map", tags=[tags.MAP.name], route_handlers=[MapController])

    statistics_route_handler = Router(
        path="/statistics",
        tags=[tags.STATISTICS.name],
        route_handlers=[StatisticsController],
    )

    events_route_handler = Router(
        path="/events",
        tags=[tags.EVENTS.name],
        route_handlers=[EventsApiController],
    )

    delays_route_handler = Router(
        path="/delays",
        tags=[tags.DELAYS.name],
        route_handlers=[DelaysApiController],
    )

    return Router(
        path="/api/v1",
        route_handlers=[
            agency_route_handler,
            calendar_route_handler,
            calendar_date_route_handler,
            route_route_handler,
            trip_route_handler,
            stop_route_handler,
            shape_route_handler,
            stop_time_handler,
            realtime_route_handler,
            schedule_route_handler,
            maps_route_handler,
            statistics_route_handler,
            events_route_handler,
            delays_route_handler,
        ],
    )
