import pytest
from litestar.testing import AsyncTestClient

pytestmark = pytest.mark.asyncio(loop_scope="session")

unknown_paths = ["/fakeroute", "/api/fakeroute"]


@pytest.mark.parametrize("url", unknown_paths)
async def test_unknown_path_returns_json_404_without_html_accept(
    async_client: AsyncTestClient, url: str
) -> None:
    response = await async_client.get(url)
    assert response.status_code == 404
    assert response.json()["path"] == url


@pytest.mark.parametrize("url", unknown_paths)
async def test_unknown_path_returns_html_404_when_accept_is_html(
    async_client: AsyncTestClient, url: str
) -> None:
    response = await async_client.get(url, headers={"accept": "text/html"})
    assert response.status_code == 404
    assert response.headers["content-type"] == "text/html; charset=utf-8"
    assert "404 Not Found" in response.text
    assert "The requested URL was not found on the server" in response.text
