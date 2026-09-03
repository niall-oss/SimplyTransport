import pytest
from litestar.testing import AsyncTestClient

pytestmark = pytest.mark.asyncio(loop_scope="session")

docs_urls = [
    "",
    "/swagger/",
    "/elements",
    "/redoc",
    "/rapidoc",
    "/scalar",
    "/openapi.json",
    "/openapi.yaml",
]


@pytest.mark.parametrize("url", docs_urls)
async def test_docs_renderer_returns_200(async_client: AsyncTestClient, url: str) -> None:
    response = await async_client.get(f"/docs{url}")
    assert response.status_code == 200


async def test_default_is_stoplight(async_client: AsyncTestClient) -> None:
    response = await async_client.get("/docs")
    assert response.status_code == 200
    assert "stoplight" in response.text
    assert "elements" in response.text
