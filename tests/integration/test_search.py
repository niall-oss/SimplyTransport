import pytest
from litestar.testing import AsyncTestClient

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_stop_search_returns_harristown_for_name_query(async_client: AsyncTestClient) -> None:
    response = await async_client.get("/search/stops?search=Harristown")
    assert response.status_code == 200
    assert "Harristown" in response.text
    assert "No stops found" not in response.text


async def test_route_search_returns_route_4(async_client: AsyncTestClient) -> None:
    response = await async_client.get("/search/routes?search=4")
    assert response.status_code == 200
    assert ">4<" in response.text or "Monkstown Avenue - Harristown" in response.text
    assert "No routes found" not in response.text
