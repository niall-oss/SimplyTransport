from enum import IntEnum, StrEnum
from typing import Annotated, Any

from pydantic import BeforeValidator
from SimplyTransport.domain import enums as domain_enums


def coerce_from_domain[E: IntEnum | StrEnum](domain_cls: type[E]) -> BeforeValidator:
    def _coerce(value: Any) -> Any:
        if value is None:
            return value
        if isinstance(value, domain_cls):
            return value.name
        if isinstance(value, IntEnum):
            return value.name
        if isinstance(value, int) and not isinstance(value, bool) and issubclass(domain_cls, IntEnum):
            return domain_cls(value).name
        if isinstance(value, str) and issubclass(domain_cls, StrEnum):
            try:
                return domain_cls(value).name
            except ValueError:
                return value
        return value

    return BeforeValidator(_coerce)


def to_domain[E: IntEnum](value: StrEnum, domain_cls: type[E]) -> E:
    return domain_cls[value.name]


class Direction(StrEnum):
    OUTBOUND = "OUTBOUND"
    INBOUND = "INBOUND"


class RouteType(StrEnum):
    TRAM = "TRAM"
    SUBWAY = "SUBWAY"
    RAIL = "RAIL"
    BUS = "BUS"
    FERRY = "FERRY"
    CABLE_TRAM = "CABLE_TRAM"
    AERIAL_LIFT = "AERIAL_LIFT"
    FUNICULAR = "FUNICULAR"
    TROLLEYBUS = "TROLLEYBUS"
    MONORAIL = "MONORAIL"


class DayOfWeek(StrEnum):
    MONDAY = "MONDAY"
    TUESDAY = "TUESDAY"
    WEDNESDAY = "WEDNESDAY"
    THURSDAY = "THURSDAY"
    FRIDAY = "FRIDAY"
    SATURDAY = "SATURDAY"
    SUNDAY = "SUNDAY"


class LocationType(StrEnum):
    STOP = "STOP"
    STATION = "STATION"
    ENTRANCE_EXIT = "ENTRANCE_EXIT"
    GENERIC_NODE = "GENERIC_NODE"
    BOARDING_AREA = "BOARDING_AREA"


class PickupType(StrEnum):
    REGULARLY_SCHEDULED = "REGULARLY_SCHEDULED"
    NO_PICKUP = "NO_PICKUP"
    MUST_PHONE_AGENCY = "MUST_PHONE_AGENCY"
    MUST_COORDINATE_WITH_DRIVER = "MUST_COORDINATE_WITH_DRIVER"


class DropoffType(StrEnum):
    REGULARLY_SCHEDULED = "REGULARLY_SCHEDULED"
    NO_DROP_OFF = "NO_DROP_OFF"
    MUST_PHONE_AGENCY = "MUST_PHONE_AGENCY"
    MUST_COORDINATE_WITH_DRIVER = "MUST_COORDINATE_WITH_DRIVER"


class Timepoint(StrEnum):
    APPROXIMATE = "APPROXIMATE"
    EXACT = "EXACT"


class ExceptionType(StrEnum):
    ADDED = "ADDED"
    REMOVED = "REMOVED"


DirectionField = Annotated[Direction, coerce_from_domain(domain_enums.Direction)]
RouteTypeField = Annotated[RouteType, coerce_from_domain(domain_enums.RouteType)]
LocationTypeField = Annotated[LocationType | None, coerce_from_domain(domain_enums.LocationType)]
PickupTypeField = Annotated[PickupType | None, coerce_from_domain(domain_enums.PickupType)]
DropoffTypeField = Annotated[DropoffType | None, coerce_from_domain(domain_enums.DropoffType)]
TimepointField = Annotated[Timepoint | None, coerce_from_domain(domain_enums.Timepoint)]
ExceptionTypeField = Annotated[ExceptionType, coerce_from_domain(domain_enums.ExceptionType)]
