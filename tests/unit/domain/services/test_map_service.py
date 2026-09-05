from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock

import pytest
from advanced_alchemy.exceptions import NotFoundError
from SimplyTransport.api_contracts.map_contracts import GeoJSONLineString, RouteLayer
from SimplyTransport.domain.maps.colors import Colors
from SimplyTransport.domain.maps.enums import StaticStopMapTypes
from SimplyTransport.domain.realtime.vehicle.rt_vehicle_model import RTVehicleModel
from SimplyTransport.domain.services.map_service import MapService, _vehicle_point_from_rt
from SimplyTransport.domain.stop.stop_model import StopModel


def _service(**overrides: Any) -> tuple[MapService, dict[str, AsyncMock]]:
    repos = {
        "stop_repo": AsyncMock(),
        "route_repo": AsyncMock(),
        "shape_repo": AsyncMock(),
        "trip_repo": AsyncMock(),
        "rt_vehicle_repo": AsyncMock(),
    }
    repos.update(overrides)
    return MapService(**repos), repos


def _stop(stop_id: str = "S1", lat: float | None = 53.3, lon: float | None = -6.2, **extra: Any):
    return SimpleNamespace(id=stop_id, code="c1", name="Stop", lat=lat, lon=lon, **extra)


def _route(route_id: str = "R1", short_name: str = "4", long_name: str = "Route 4"):
    return SimpleNamespace(id=route_id, short_name=short_name, long_name=long_name)


def _trip(route_id: str = "R1", shape_id: str = "SH1"):
    return SimpleNamespace(route_id=route_id, shape_id=shape_id)


def _shape(shape_id: str = "SH1", lat: float = 53.3, lon: float = -6.2, sequence: int = 1):
    return SimpleNamespace(shape_id=shape_id, lat=lat, lon=lon, sequence=sequence)


def _vehicle(route_id: str = "R1", agency_name: str | None = "Dublin Bus"):
    agency = None if agency_name is None else SimpleNamespace(name=agency_name)
    route = SimpleNamespace(id=route_id, short_name="4", agency=agency)
    return SimpleNamespace(
        lat=53.4,
        lon=-6.3,
        vehicle_id=9,
        trip_id="T1",
        time_of_update=datetime(2026, 3, 21, 12, 0, tzinfo=UTC),
        trip=SimpleNamespace(route_id=route_id, route=route),
    )


def test_map_service_init():
    stop_repo = AsyncMock()
    route_repo = AsyncMock()
    shape_repo = AsyncMock()
    trip_repo = AsyncMock()
    rt_vehicle_repo = AsyncMock()
    map_service = MapService(stop_repo, route_repo, shape_repo, trip_repo, rt_vehicle_repo)
    assert map_service.stop_repo is stop_repo
    assert map_service.route_repo is route_repo
    assert map_service.shape_repo is shape_repo
    assert map_service.trip_repo is trip_repo
    assert map_service.rt_vehicle_repo is rt_vehicle_repo


@pytest.mark.asyncio
async def test_build_stop_map_payload_returns_none_without_coords():
    svc, repos = _service()
    repos["stop_repo"].get = AsyncMock(return_value=_stop(lat=None, lon=None))
    repos["stop_repo"].get_direction_of_stop = AsyncMock(return_value=0)
    repos["route_repo"].get_routes_by_stop_id_with_agency = AsyncMock(return_value=[_route()])
    assert await svc.build_stop_map_payload("S1") is None


@pytest.mark.asyncio
async def test_build_stop_map_payload_skips_routes_without_trip_or_shape():
    svc, repos = _service()
    focus = _stop()
    other = _stop("S2", lat=None, lon=None)
    with_coords = _stop("S3", lat=53.31, lon=-6.21)
    repos["stop_repo"].get = AsyncMock(return_value=focus)
    repos["stop_repo"].get_direction_of_stop = AsyncMock(return_value=0)
    repos["route_repo"].get_routes_by_stop_id_with_agency = AsyncMock(
        return_value=[_route("R1"), _route("R2"), _route("R3")]
    )
    repos["trip_repo"].get_first_trips_by_route_ids = AsyncMock(
        return_value=[_trip("R1", "SH1"), _trip("R3", "SH3")]
    )
    repos["rt_vehicle_repo"].get_vehicles_on_routes = AsyncMock(return_value=[_vehicle("R1")])
    repos["shape_repo"].get_sequence_sorted_shapes_by_shape_ids = AsyncMock(return_value=[_shape("SH1")])
    repos["stop_repo"].get_stops_by_route_ids = AsyncMock(return_value=[focus, other, with_coords])

    payload = await svc.build_stop_map_payload("S1")
    assert payload is not None
    assert payload.focus_stop_id == "S1"
    assert [layer.route_id for layer in payload.routes] == ["R1"]
    assert payload.vehicles[0].agency_name == "Dublin Bus"
    assert {s.stop_id for s in payload.stops} == {"S1", "S3"}


@pytest.mark.asyncio
async def test_build_route_map_payload_raises_when_trip_missing():
    svc, repos = _service()
    repos["route_repo"].get_by_id_with_agency = AsyncMock(return_value=_route())
    repos["trip_repo"].get_first_trip_by_route_id = AsyncMock(return_value=None)
    with pytest.raises(NotFoundError, match="No trip found"):
        await svc.build_route_map_payload("R1", 0)


@pytest.mark.asyncio
async def test_build_route_map_payload_raises_when_shapes_missing():
    svc, repos = _service()
    repos["route_repo"].get_by_id_with_agency = AsyncMock(return_value=_route())
    repos["trip_repo"].get_first_trip_by_route_id = AsyncMock(return_value=_trip())
    repos["shape_repo"].get_sequence_sorted_shapes_by_shape_id = AsyncMock(return_value=[])
    with pytest.raises(NotFoundError, match="No shapes found"):
        await svc.build_route_map_payload("R1", 0)


@pytest.mark.asyncio
async def test_build_route_map_payload_drops_stops_without_coords():
    svc, repos = _service()
    repos["route_repo"].get_by_id_with_agency = AsyncMock(return_value=_route())
    repos["trip_repo"].get_first_trip_by_route_id = AsyncMock(return_value=_trip())
    repos["shape_repo"].get_sequence_sorted_shapes_by_shape_id = AsyncMock(
        return_value=[_shape(lat=53.4, lon=-6.4)]
    )
    repos["rt_vehicle_repo"].get_vehicles_on_routes = AsyncMock(return_value=[_vehicle(agency_name=None)])
    repos["stop_repo"].get_stops_by_route_id = AsyncMock(
        return_value=[_stop("S1"), _stop("S2", lat=None, lon=None)]
    )
    payload = await svc.build_route_map_payload("R1", 0)
    assert payload.center == (-6.4, 53.4)
    assert [s.stop_id for s in payload.stops] == ["S1"]
    assert payload.vehicles[0].agency_name == ""


@pytest.mark.asyncio
async def test_build_nearby_map_payload_drops_null_coords():
    svc, repos = _service()
    repos["stop_repo"].get_stops_near_location = AsyncMock(
        return_value=[_stop("S1"), _stop("S2", lat=None, lon=-6.2)]
    )
    payload = await svc.build_nearby_map_payload(53.3, -6.2, 900)
    assert payload.radius_meters == 900
    assert [s.stop_id for s in payload.stops] == ["S1"]


@pytest.mark.asyncio
async def test_build_agency_routes_map_payload_all_and_specific():
    svc, repos = _service()
    repos["route_repo"].get_with_agencies = AsyncMock(return_value=[_route()])
    repos["trip_repo"].get_first_trips_by_route_ids = AsyncMock(return_value=[_trip()])
    repos["shape_repo"].get_sequence_sorted_shapes_by_shape_ids = AsyncMock(return_value=[_shape()])
    all_payload = await svc.build_agency_routes_map_payload("All")
    assert all_payload.agency_id == "All"
    repos["route_repo"].get_with_agencies_by_agency_id = AsyncMock(return_value=[_route("R2")])
    repos["trip_repo"].get_first_trips_by_route_ids = AsyncMock(return_value=[_trip("R2")])
    repos["shape_repo"].get_sequence_sorted_shapes_by_shape_ids = AsyncMock(return_value=[_shape("SH1")])
    one = await svc.build_agency_routes_map_payload("AG1")
    assert one.agency_id == "AG1"
    repos["route_repo"].get_with_agencies_by_agency_id.assert_awaited_once_with("AG1")


@pytest.mark.asyncio
async def test_build_agency_routes_map_payload_raises_when_no_routes():
    svc, repos = _service()
    repos["route_repo"].get_with_agencies_by_agency_id = AsyncMock(return_value=[])
    with pytest.raises(ValueError, match="No routes found"):
        await svc.build_agency_routes_map_payload("missing")


@pytest.mark.asyncio
async def test_build_agency_routes_map_payload_raises_when_no_geometry():
    svc, repos = _service()
    repos["route_repo"].get_with_agencies_by_agency_id = AsyncMock(return_value=[_route()])
    repos["trip_repo"].get_first_trips_by_route_ids = AsyncMock(return_value=[])
    repos["shape_repo"].get_sequence_sorted_shapes_by_shape_ids = AsyncMock(return_value=[])
    with pytest.raises(ValueError, match="No route geometry"):
        await svc.build_agency_routes_map_payload("AG1")


@pytest.mark.parametrize(
    ("map_type", "repo_method"),
    [
        (StaticStopMapTypes.ALL_STOPS, "get_all_with_stop_feature"),
        (StaticStopMapTypes.REALTIME_DISPLAYS, "get_stops_with_realtime_displays"),
        (StaticStopMapTypes.SHELTERED_STOPS, "get_stops_with_shelters"),
        (StaticStopMapTypes.UNSURVEYED, "get_stops_that_are_unsurveyed"),
    ],
)
@pytest.mark.asyncio
async def test_build_static_stop_map_payload_uses_map_type_repo(map_type, repo_method):
    svc, repos = _service()
    getattr(repos["stop_repo"], repo_method).return_value = [_stop("S1"), _stop("S2", lat=None)]
    payload = await svc.build_static_stop_map_payload(map_type)
    assert payload.map_type == map_type.value
    assert [s.stop_id for s in payload.stops] == ["S1"]
    getattr(repos["stop_repo"], repo_method).assert_awaited_once()


def test_center_helpers_fall_back_to_ireland_default():
    default = MapService._default_map_center()
    assert MapService._center_from_stops([]) == default
    assert MapService._center_from_stops(cast(list[StopModel], [_stop(lat=None, lon=None)])) == default
    assert MapService._center_from_stops(
        cast(list[StopModel], [_stop(lat=53.0, lon=-6.0), _stop(lat=55.0, lon=-8.0)])
    ) == (
        -7.0,
        54.0,
    )
    empty_layer = RouteLayer(
        route_id="R1",
        short_name="4",
        long_name="x",
        color="#000",
        line=GeoJSONLineString(coordinates=[]),
    )
    assert MapService._center_from_route_layers([]) == default
    assert MapService._center_from_route_layers([empty_layer]) == default
    layer = RouteLayer(
        route_id="R1",
        short_name="4",
        long_name="x",
        color="#000",
        line=GeoJSONLineString(coordinates=[[-6.0, 53.0], [-8.0, 55.0]]),
    )
    assert MapService._center_from_route_layers([layer]) == (-8.0, 55.0)


def test_vehicle_point_from_rt_uses_color_and_blank_agency():
    point = _vehicle_point_from_rt(
        cast(RTVehicleModel, _vehicle(agency_name=None)), "R1", Colors.BLUE.to_hex()
    )
    assert point.route_id == "R1"
    assert point.color == Colors.BLUE.to_hex()
    assert point.agency_name == ""
