import pytest
from litestar.testing import AsyncTestClient

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_routes_list_returns_all_routes(async_client: AsyncTestClient) -> None:
    response = await async_client.get("api/v1/route/")
    assert response.status_code == 200
    routes = response.json()
    assert len(routes) == 2
    assert routes[0]["id"] == "3623_54684"
    assert routes[0]["short_name"] == "4"
    assert routes[1]["id"] == "3623_54691"
    assert routes[1]["short_name"] == "9"


async def test_routes_filtered_by_agency_id_return_that_agency(async_client: AsyncTestClient) -> None:
    response = await async_client.get("api/v1/route/?agencyId=7778019")
    assert response.status_code == 200
    routes = response.json()
    assert len(routes) == 2
    assert all(route["agency_id"] == "7778019" for route in routes)


async def test_routes_filtered_by_agency_id_return_404_when_none(async_client: AsyncTestClient) -> None:
    response = await async_client.get("api/v1/route/?agencyId=7778801877788018")
    assert response.status_code == 404
    assert response.json()["detail"] == "Routes not found with agency id 7778801877788018"


async def test_routes_count_includes_total(async_client: AsyncTestClient) -> None:
    response = await async_client.get("api/v1/route/count")
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == len(payload["routes"]) == 2


async def test_routes_count_filtered_by_agency_id_includes_total(async_client: AsyncTestClient) -> None:
    response = await async_client.get("api/v1/route/count?agencyId=7778019")
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == len(payload["routes"]) == 2


async def test_routes_count_filtered_by_agency_id_return_404_when_none(
    async_client: AsyncTestClient,
) -> None:
    response = await async_client.get("api/v1/route/count?agencyId=7778801877788018")
    assert response.status_code == 404
    assert response.json()["detail"] == "Routes not found with agency id 7778801877788018"


async def test_route_returns_match_for_known_id(async_client: AsyncTestClient) -> None:
    response = await async_client.get("api/v1/route/3623_54684")
    assert response.status_code == 200
    route = response.json()
    assert route["id"] == "3623_54684"
    assert route["short_name"] == "4"
    assert route["long_name"] == "Monkstown Avenue - Harristown"


async def test_route_returns_404_for_unknown_id(async_client: AsyncTestClient) -> None:
    response = await async_client.get("api/v1/route/3623_54691_")
    assert response.status_code == 404
    assert response.json()["detail"] == "Route not found with id 3623_54691_"
