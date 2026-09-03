from urllib.parse import quote

import pytest
from litestar.testing import AsyncTestClient

pytestmark = pytest.mark.asyncio(loop_scope="session")

HARRISTOWN_LAT = "53.41772"
HARRISTOWN_LON = "-6.27864"


async def test_stop_map_returns_json(async_client: AsyncTestClient) -> None:
    response = await async_client.get("/api/v1/map/stop/8250DB002026")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload["center"]) == 2
    assert "focus_stop_id" in payload
    assert isinstance(payload["routes"], list)
    assert isinstance(payload["stops"], list)
    if payload["stops"]:
        assert "stop_id" in payload["stops"][0]
        assert "routes" not in payload["stops"][0]


async def test_stop_map_returns_404_if_stop_not_found(async_client: AsyncTestClient) -> None:
    response = await async_client.get("/api/v1/map/stop/fakestop")
    assert response.status_code == 404
    assert response.json()["detail"] == "Stop not found with id fakestop"


async def test_route_map_returns_json(async_client: AsyncTestClient) -> None:
    response = await async_client.get("/api/v1/map/route/3623_54684/0")
    assert response.status_code == 200
    payload = response.json()
    assert payload.get("zoom") == 12
    assert payload["route"]["route_id"] == "3623_54684"
    assert isinstance(payload["stops"], list)


async def test_route_map_returns_404_if_route_not_found(async_client: AsyncTestClient) -> None:
    response = await async_client.get("/api/v1/map/route/fakeroute_id/0")
    assert response.status_code == 404
    assert response.json()["detail"] == "Route map not found for route fakeroute_id and direction 0"


async def test_nearby_map_returns_stops_around_point(async_client: AsyncTestClient) -> None:
    response = await async_client.get(
        f"/api/v1/map/stop/nearby?latitude={HARRISTOWN_LAT}&longitude={HARRISTOWN_LON}"
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["radius_meters"] == 1200
    assert payload.get("zoom") == 15
    assert len(payload["stops"]) >= 1


async def test_nearby_map_accepts_radius_meters(async_client: AsyncTestClient) -> None:
    response = await async_client.get(
        f"/api/v1/map/stop/nearby?latitude={HARRISTOWN_LAT}&longitude={HARRISTOWN_LON}&radius_meters=900"
    )
    assert response.status_code == 200
    assert response.json()["radius_meters"] == 900


@pytest.mark.parametrize("radius_meters", [0, 1501])
async def test_nearby_map_rejects_radius_meters_out_of_range(
    async_client: AsyncTestClient, radius_meters: int
) -> None:
    response = await async_client.get(
        f"/api/v1/map/stop/nearby?latitude={HARRISTOWN_LAT}&longitude={HARRISTOWN_LON}"
        f"&radius_meters={radius_meters}"
    )
    assert response.status_code == 400


async def test_agency_map_returns_404_for_unknown_agency(async_client: AsyncTestClient) -> None:
    response = await async_client.get("/api/v1/map/route/agency/__no_such_agency__")
    assert response.status_code == 404
    assert "No routes found" in response.json().get("detail", "")


async def test_static_stop_map_returns_json(async_client: AsyncTestClient) -> None:
    map_type = quote("All Stops")
    response = await async_client.get(f"/api/v1/map/stop/aggregated/{map_type}")
    assert response.status_code == 200
    payload = response.json()
    assert "map_type" in payload
    assert isinstance(payload["stops"], list)


async def test_static_stop_map_returns_400_for_invalid_map_type(async_client: AsyncTestClient) -> None:
    response = await async_client.get("/api/v1/map/stop/aggregated/not-a-valid-map-type")
    assert response.status_code == 400
