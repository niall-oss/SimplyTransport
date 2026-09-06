from enum import IntEnum, StrEnum


class Direction(IntEnum):
    """Direction of travel."""

    OUTBOUND = 0
    INBOUND = 1


class ExceptionType(StrEnum):
    ADDED = "added"
    REMOVED = "removed"


class RouteType(IntEnum):
    TRAM = 0
    SUBWAY = 1
    RAIL = 2
    BUS = 3
    FERRY = 4
    CABLE_TRAM = 5
    AERIAL_LIFT = 6
    FUNICULAR = 7
    TROLLEYBUS = 11
    MONORAIL = 12


class DayOfWeek(IntEnum):
    MONDAY = 0
    TUESDAY = 1
    WEDNESDAY = 2
    THURSDAY = 3
    FRIDAY = 4
    SATURDAY = 5
    SUNDAY = 6


class LocationType(IntEnum):
    STOP = 0
    STATION = 1
    ENTRANCE_EXIT = 2
    GENERIC_NODE = 3
    BOARDING_AREA = 4


class PickupType(IntEnum):
    """Indicates pickup method"""

    REGULARLY_SCHEDULED = 0
    NO_PICKUP = 1
    MUST_PHONE_AGENCY = 2
    MUST_COORDINATE_WITH_DRIVER = 3


class DropoffType(IntEnum):
    """Indicates dropoff method"""

    REGULARLY_SCHEDULED = 0
    NO_DROP_OFF = 1
    MUST_PHONE_AGENCY = 2
    MUST_COORDINATE_WITH_DRIVER = 3


class Timepoint(IntEnum):
    """Indicates if arrival and departure times for a stop are strictly adhered to by the vehicle
    or if they are instead approximate and/or interpolated times
    A null value here means EXACT
    """

    APPROXIMATE = 0
    EXACT = 1


class StopType(StrEnum):
    """Type marked (MKD) indicates the stops is marked with a physical
    transport infrastructure item (pole, shelter or real time unit). Customs
    and Practice (CUS) indicates there is no such infrastructure
    """

    MARKED = "MKD"
    CUSTOMS = "CUS"
    UNKNOWN = "Unknown"


class Bearing(StrEnum):
    """Bearing indicates the direction that traffic travels"""

    NORTH = "N"
    NORTH_EAST = "NE"
    EAST = "E"
    SOUTH_EAST = "SE"
    SOUTH = "S"
    SOUTH_WEST = "SW"
    WEST = "W"
    NORTH_WEST = "NW"
    UNKNOWN = "U"
