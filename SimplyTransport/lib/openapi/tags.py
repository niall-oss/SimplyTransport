from litestar.openapi.spec import Tag


class Tags:
    AGENCY = Tag(
        name="Agency",
        description="Transport operators",
    )
    ROUTE = Tag(
        name="Route",
        description="A group of trips shown to riders as one service",
    )
    STOP = Tag(
        name="Stop",
        description="Places where vehicles pick up and drop off riders",
    )
    TRIP = Tag(
        name="Trip",
        description="A sequence of two or more stops at specific times",
    )
    STOP_TIME = Tag(
        name="StopTime",
        description="Arrival and departure times at each stop on a trip",
    )
    CALENDAR = Tag(
        name="Calendar",
        description="Weekly service pattern for a service_id",
    )
    CALENDAR_DATE = Tag(
        name="CalendarDate",
        description="Dates when a calendar service is added or removed",
    )
    SHAPE = Tag(
        name="Shape",
        description="The path a vehicle travels along a route",
    )
    REALTIME = Tag(
        name="Realtime",
        description="Live arrivals at a stop, overlaid on the static timetable",
    )
    SCHEDULE = Tag(
        name="Schedule",
        description="Static timetable for a stop",
    )
    MAP = Tag(
        name="Map",
        description="JSON for MapLibre: route lines, stops, and vehicles",
    )
    STATISTICS = Tag(
        name="Statistics",
        description="Counts and summaries of stored data",
    )
    EVENTS = Tag(
        name="Events",
        description="Records of system jobs such as GTFS imports and cleanup",
    )
    DELAYS = Tag(
        name="Delays",
        description="Historical early and late arrivals, in seconds",
    )

    @classmethod
    def list_all_tags(cls) -> list[Tag]:
        return [value for key, value in cls.__dict__.items() if isinstance(value, Tag)]
