import pytest
from litestar.testing import AsyncTestClient

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_delays_route_page_renders_for_known_route(async_client: AsyncTestClient) -> None:
    response = await async_client.get("/delays/route/4")
    assert response.status_code == 200
    html = response.text
    assert "Historical Delays" in html
    assert "No historical data available for this route." not in html
    assert "Samples" in html
