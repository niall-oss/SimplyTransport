import pytest
from litestar.testing import AsyncTestClient

pytestmark = pytest.mark.asyncio(loop_scope="session")

pages = [
    ("/stops/", "Stop Search"),
    ("/routes/", "Route Search"),
    ("/maps", "Transport Maps"),
    ("/stats", "Statistics"),
    ("/apidocs", "API Documentation"),
    ("/delays-explained", "Historical Delay Data"),
    ("/about", "About SimplyTransport"),
    ("/search/stops/nearby?latitude=53.41772&longitude=-6.27864", "Stops Nearby"),
]


@pytest.mark.parametrize(("url", "needle"), pages, ids=[url.split("?")[0] for url, _ in pages])
async def test_page_renders(async_client: AsyncTestClient, url: str, needle: str) -> None:
    response = await async_client.get(url)
    assert response.status_code == 200
    assert needle in response.text


async def test_exception_page_returns_500(async_client: AsyncTestClient) -> None:
    response = await async_client.get("/exception", headers={"accept": "text/html"})
    assert response.status_code == 500
    assert "500 Error" in response.text
