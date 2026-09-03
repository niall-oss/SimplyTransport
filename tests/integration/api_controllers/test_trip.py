import pytest
from litestar.testing import AsyncTestClient

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_trip_returns_match_for_known_id(async_client: AsyncTestClient) -> None:
    response = await async_client.get("api/v1/trip/3623_8603")
    assert response.status_code == 200
    trip = response.json()
    assert trip["id"] == "3623_8603"
    assert trip["route_id"] == "3623_54684"
    assert trip["service_id"] == "290"
    assert trip["headsign"] == "Monkstown Ave"
    assert trip["short_name"] == "2616"
    assert trip["direction"] == 0
    assert trip["block_id"] == "4002"
    assert trip["dataset"] == "TFI"


async def test_trip_returns_404_for_unknown_id(async_client: AsyncTestClient) -> None:
    response = await async_client.get("api/v1/trip/3623_860544")
    assert response.status_code == 404
    assert response.json()["detail"] == "Trip not found with id 3623_860544"


async def test_trips_by_route_return_only_that_route(async_client: AsyncTestClient) -> None:
    response = await async_client.get("api/v1/trip/route/3623_54684")
    assert response.status_code == 200
    trips = response.json()
    assert len(trips) == 383
    assert all(trip["route_id"] == "3623_54684" for trip in trips)


async def test_trips_by_route_return_empty_for_unknown_route(async_client: AsyncTestClient) -> None:
    response = await async_client.get("api/v1/trip/route/not_a_route")
    assert response.status_code == 200
    assert response.json() == []


async def test_trips_by_route_count_includes_total(async_client: AsyncTestClient) -> None:
    response = await async_client.get("api/v1/trip/route/count/3623_54684")
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == len(payload["trips"]) == 383
