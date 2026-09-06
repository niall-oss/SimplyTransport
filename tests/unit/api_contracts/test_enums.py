from datetime import date

from SimplyTransport.api_contracts.calendar_date_contracts import CalendarDate
from SimplyTransport.api_contracts.enums import ExceptionType, RouteType, to_domain
from SimplyTransport.api_contracts.route_contracts import Route
from SimplyTransport.domain.enums import ExceptionType as DomainExceptionType
from SimplyTransport.domain.enums import RouteType as DomainRouteType


def test_to_domain_round_trips_member_name() -> None:
    assert to_domain(RouteType.BUS, DomainRouteType) is DomainRouteType.BUS
    assert to_domain(RouteType.TROLLEYBUS, DomainRouteType) is DomainRouteType.TROLLEYBUS


def test_route_contract_coerces_domain_route_type() -> None:
    route = Route.model_validate(
        {
            "id": "r1",
            "agency_id": "a1",
            "short_name": "4",
            "long_name": "Test",
            "description": None,
            "route_type": DomainRouteType.BUS,
            "url": None,
            "color": None,
            "text_color": None,
            "dataset": "TFI",
        }
    )
    assert route.route_type is RouteType.BUS

    from_int = Route.model_validate(
        {
            "id": "r1",
            "agency_id": "a1",
            "short_name": "4",
            "long_name": "Test",
            "description": None,
            "route_type": 11,
            "url": None,
            "color": None,
            "text_color": None,
            "dataset": "TFI",
        }
    )
    assert from_int.route_type is RouteType.TROLLEYBUS


def test_calendar_date_contract_coerces_domain_exception_type() -> None:
    payload = {
        "id": 1,
        "service_id": "s1",
        "date": date(2023, 10, 30),
        "exception_type": DomainExceptionType.REMOVED,
        "dataset": "TFI",
    }
    assert CalendarDate.model_validate(payload).exception_type is ExceptionType.REMOVED
    payload["exception_type"] = "removed"
    assert CalendarDate.model_validate(payload).exception_type is ExceptionType.REMOVED
