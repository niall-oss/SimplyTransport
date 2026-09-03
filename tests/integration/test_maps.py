from urllib.parse import quote

import pytest
from litestar.testing import AsyncTestClient

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_agency_route_map_page_renders_for_all(async_client: AsyncTestClient) -> None:
    response = await async_client.get("/maps/agency/route/All")
    assert response.status_code == 200
    assert "All Agencies Combined" in response.text
    assert "Sorry, this map is not available" not in response.text


async def test_stop_map_page_returns_error_for_invalid_type(async_client: AsyncTestClient) -> None:
    response = await async_client.get(f"/maps/stop/{quote('not-a-valid-map-type')}")
    assert response.status_code == 200
    assert "Sorry, this map is not available" in response.text
