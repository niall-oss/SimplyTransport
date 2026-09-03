import pytest
from litestar.testing import AsyncTestClient

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_events_paginated_returns_results(async_client: AsyncTestClient) -> None:
    response = await async_client.get("api/v1/events/")
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] >= 1
    assert len(payload["events"]) >= 1
    assert payload["events"][0]["event_type"]
    assert payload["events"][0]["created_at"]


async def test_events_paginated_by_type_returns_results(async_client: AsyncTestClient) -> None:
    response = await async_client.get("api/v1/events/gtfs.database.updated")
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] >= 1
    assert all(event["event_type"] == "gtfs.database.updated" for event in payload["events"])
    assert payload["events"][0]["created_at"]


async def test_events_paginated_by_type_return_400_for_unknown_type(async_client: AsyncTestClient) -> None:
    response = await async_client.get("api/v1/events/something.that.does.not.exist")
    assert response.status_code == 400


async def test_events_most_recent_by_type_returns_result(async_client: AsyncTestClient) -> None:
    response = await async_client.get("api/v1/events/gtfs.database.updated/most-recent")
    assert response.status_code == 200
    event = response.json()
    assert event["event_type"] == "gtfs.database.updated"
    assert event["created_at"] is not None
