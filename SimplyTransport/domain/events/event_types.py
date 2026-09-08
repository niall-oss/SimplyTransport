from enum import StrEnum

ALL_EVENTS = "all.event.types"

EVENT_TYPE_LABELS: dict[str, str] = {
    ALL_EVENTS: "All event types",
    "gtfs.database.updated": "GTFS updated",
    "realtime.database.updated": "Realtime updated",
    "realtime_vehicles.database.updated": "Vehicle positions updated",
    "stop_features.database.updated": "Stop features updated",
    "database_statistics.updated": "Statistics updated",
    "cleanup.events.deleted": "Events cleaned up",
    "cleanup.delays.deleted": "Delays cleaned up",
    "timeseries.delays.recorded": "Delays recorded",
}


def event_type_label(value: str) -> str:
    return EVENT_TYPE_LABELS.get(value, value)


class EventType(StrEnum):
    # Type of event, should be less than 255 chars long

    # GTFS
    GTFS_DATABASE_UPDATED = "gtfs.database.updated"

    # Realtime
    REALTIME_DATABASE_UPDATED = "realtime.database.updated"

    # Realtime Vehicles
    REALTIME_VEHICLES_DATABASE_UPDATED = "realtime_vehicles.database.updated"

    # Stop Features
    STOP_FEATURES_DATABASE_UPDATED = "stop_features.database.updated"

    # Database Statistics
    DATABASE_STATISTICS_UPDATED = "database_statistics.updated"

    # Cleanup
    CLEANUP_EVENTS_DELETED = "cleanup.events.deleted"
    CLEANUP_DELAYS_DELETED = "cleanup.delays.deleted"

    # Time Series
    RECORD_TS_STOP_TIMES = "timeseries.delays.recorded"
