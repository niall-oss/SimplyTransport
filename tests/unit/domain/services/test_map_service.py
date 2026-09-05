from unittest.mock import AsyncMock

from SimplyTransport.domain.services.map_service import MapService


def test_map_service_init():
    stop_repo = AsyncMock()
    route_repo = AsyncMock()
    shape_repo = AsyncMock()
    trip_repo = AsyncMock()
    rt_vehicle_repo = AsyncMock()

    map_service = MapService(
        stop_repo=stop_repo,
        route_repo=route_repo,
        shape_repo=shape_repo,
        trip_repo=trip_repo,
        rt_vehicle_repo=rt_vehicle_repo,
    )
    assert map_service.stop_repo is stop_repo
    assert map_service.route_repo is route_repo
    assert map_service.shape_repo is shape_repo
    assert map_service.trip_repo is trip_repo
    assert map_service.rt_vehicle_repo is rt_vehicle_repo
