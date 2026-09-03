import math

import pytest
from litestar.testing import AsyncTestClient

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_stop_returns_match_for_known_id(async_client: AsyncTestClient) -> None:
    response = await async_client.get("/api/v1/stop/8240DB000324")
    assert response.status_code == 200
    stop = response.json()
    assert stop["id"] == "8240DB000324"
    assert stop["code"] == "324"
    assert stop["name"] == "Harristown"
    assert stop["description"] == ""
    assert math.isclose(stop["lat"], 53.41772268, abs_tol=1e-09)
    assert math.isclose(stop["lon"], -6.278644169, abs_tol=1e-09)
    assert stop["zone_id"] == ""
    assert stop["url"] == ""
    assert stop["location_type"] is None
    assert stop["parent_station"] is None
    assert stop["dataset"] == "TFI"


async def test_stop_returns_404_for_unknown_id(async_client: AsyncTestClient) -> None:
    response = await async_client.get("/api/v1/stop/8240DB0003241")
    assert response.status_code == 404
    assert response.json()["detail"] == "Stop not found with id 8240DB0003241"


async def test_stop_detailed_includes_routes_and_features(async_client: AsyncTestClient) -> None:
    response = await async_client.get("/api/v1/stop/8240DB000324/detailed")
    assert response.status_code == 200
    payload = response.json()
    assert payload["stop"]["id"] == "8240DB000324"
    assert isinstance(payload["routes"], list)
    assert len(payload["routes"]) >= 1
    assert "route_id" in payload["routes"][0]
    assert "stop_features" in payload
    assert isinstance(payload["street_view_url"], str)


async def test_stop_detailed_returns_404_for_unknown_id(async_client: AsyncTestClient) -> None:
    response = await async_client.get("/api/v1/stop/__no_such_stop__/detailed")
    assert response.status_code == 404
    assert response.json()["detail"] == "Stop not found with id __no_such_stop__"


async def test_stop_returns_match_for_known_code(async_client: AsyncTestClient) -> None:
    response = await async_client.get("/api/v1/stop/code/324")
    assert response.status_code == 200
    stop = response.json()
    assert stop["id"] == "8240DB000324"
    assert stop["code"] == "324"
    assert stop["name"] == "Harristown"


async def test_stop_returns_404_for_unknown_code(async_client: AsyncTestClient) -> None:
    response = await async_client.get("/api/v1/stop/code/3241")
    assert response.status_code == 404
    assert response.json()["detail"] == "Stop not found with code 3241"


async def test_search_stops_returns_match_for_name_prefix(async_client: AsyncTestClient) -> None:
    response = await async_client.get("/api/v1/stop/search?search=harris")
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["id"] == "8240DB000324"
    assert payload["items"][0]["name"] == "Harristown"


async def test_search_stops_returns_match_for_code(async_client: AsyncTestClient) -> None:
    response = await async_client.get("/api/v1/stop/search?search=324")
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["id"] == "8240DB000324"


async def test_search_stops_paginates_with_limit_and_offset(async_client: AsyncTestClient) -> None:
    response = await async_client.get("/api/v1/stop/search?search=Harristown&currentPage=1&pageSize=10")
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["offset"] == 0
    assert payload["limit"] == 10
    assert len(payload["items"]) == 1


async def test_search_stops_returns_404_when_page_is_empty(async_client: AsyncTestClient) -> None:
    response = await async_client.get("/api/v1/stop/search?search=Harristown&currentPage=2&pageSize=10")
    assert response.status_code == 404
