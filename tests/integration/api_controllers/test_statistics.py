from datetime import UTC, datetime

import pytest
from litestar.testing import AsyncTestClient

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_statistics_most_recent_returns_gtfs_counts(async_client: AsyncTestClient) -> None:
    response = await async_client.get("api/v1/statistics/gtfs.record.counts")
    assert response.status_code == 200
    rows = response.json()
    assert len(rows) == 9
    assert all(row["statistic_type"] == "gtfs.record.counts" for row in rows)
    assert "key" in rows[0]
    assert isinstance(rows[0]["value"], int)


async def test_statistics_most_recent_returns_operator_route_counts(async_client: AsyncTestClient) -> None:
    response = await async_client.get("api/v1/statistics/operator.route.counts")
    assert response.status_code == 200
    rows = response.json()
    assert len(rows) == 1
    assert rows[0]["statistic_type"] == "operator.route.counts"


async def test_statistics_on_day_returns_gtfs_counts(async_client: AsyncTestClient) -> None:
    current_day = datetime.now(UTC).date().isoformat()
    response = await async_client.get(f"api/v1/statistics/gtfs.record.counts/{current_day}")
    assert response.status_code == 200
    rows = response.json()
    assert len(rows) == 9
    assert all(row["statistic_type"] == "gtfs.record.counts" for row in rows)


async def test_statistics_on_day_returns_404_when_none(async_client: AsyncTestClient) -> None:
    response = await async_client.get("api/v1/statistics/gtfs.record.counts/2021-01-01")
    assert response.status_code == 404
