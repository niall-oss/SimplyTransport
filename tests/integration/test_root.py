import pytest
from litestar.testing import AsyncTestClient

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_home_page_returns_welcome(async_client: AsyncTestClient) -> None:
    response = await async_client.get("/")
    assert response.status_code == 200
    assert "Welcome to SimplyTransport" in response.text


async def test_healthcheck_returns_ok(async_client: AsyncTestClient) -> None:
    response = await async_client.get("/healthcheck")
    assert response.status_code == 200
    assert response.text == "OK"
