import pytest
from litestar.testing import AsyncTestClient

pytestmark = pytest.mark.asyncio(loop_scope="session")

stats_partials = [
    ("/stats/static/most-recent", "Current Static Database Statistics"),
    ("/stats/operators/most-recent", "Operator Route Data"),
    ("/stats/stop-features/most-recent", "Stop Features"),
    ("/stats/delays/most-recent", "Delay Records"),
]


@pytest.mark.parametrize(("url", "needle"), stats_partials, ids=[url for url, _ in stats_partials])
async def test_stats_partial_renders_table(async_client: AsyncTestClient, url: str, needle: str) -> None:
    response = await async_client.get(url)
    assert response.status_code == 200
    assert needle in response.text
    assert "<table" in response.text
