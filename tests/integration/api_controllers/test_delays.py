from urllib.parse import quote

import pytest
from litestar.testing import AsyncTestClient

pytestmark = pytest.mark.asyncio(loop_scope="session")

_DELAY_PATH = f"/api/v1/delays/8240DB000324/4/{quote('08:00:00', safe='')}"


async def test_delays_return_rows_for_stop_route_and_time(async_client: AsyncTestClient) -> None:
    response = await async_client.get(_DELAY_PATH)
    assert response.status_code == 200
    rows = response.json()
    assert len(rows) == 3
    assert {row["delay_in_minutes"] for row in rows} == {1.0, 2.0, 3.0}
    assert all(row["stop_id"] == "8240DB000324" for row in rows)
    assert all(row["route_code"] == "4" for row in rows)


async def test_delays_truncated_return_graph_points_for_stop_route_and_time(
    async_client: AsyncTestClient,
) -> None:
    response = await async_client.get(f"{_DELAY_PATH}/truncated")
    assert response.status_code == 200
    rows = response.json()
    assert len(rows) == 3
    assert "timestamp" in rows[0]
    assert "delay_in_minutes" in rows[0]


async def test_delays_aggregated_return_stats_for_stop_route_and_time(
    async_client: AsyncTestClient,
) -> None:
    response = await async_client.get(f"{_DELAY_PATH}/aggregated")
    assert response.status_code == 200
    stats = response.json()
    assert stats["samples"] == 3
    assert stats["avg"] == 120


async def test_delays_aggregated_return_stats_for_route(async_client: AsyncTestClient) -> None:
    response = await async_client.get("/api/v1/delays/4/aggregated")
    assert response.status_code == 200
    stats = response.json()
    assert stats["samples"] == 3
    assert stats["avg"] == 120


async def test_delays_aggregated_return_404_when_no_samples(async_client: AsyncTestClient) -> None:
    missing = f"/api/v1/delays/unknown-stop/unknown-route/{quote('09:00:00', safe='')}/aggregated"
    response = await async_client.get(missing)
    assert response.status_code == 404


async def test_delays_return_400_when_start_is_after_end(async_client: AsyncTestClient) -> None:
    # Use a path this suite has not cached; delay cache keys ignore query times.
    path = f"/api/v1/delays/8240DB000324/4/{quote('09:00:00', safe='')}"
    response = await async_client.get(f"{path}?start_time=2026-01-02T00:00:00Z&end_time=2026-01-01T00:00:00Z")
    assert response.status_code == 400
    assert "Start time cannot be greater than end time" in response.json()["detail"]
