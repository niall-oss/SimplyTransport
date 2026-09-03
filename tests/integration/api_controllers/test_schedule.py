import pytest
from litestar.testing import AsyncTestClient

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_schedule_returns_rows_for_stop_in_time_window(async_client: AsyncTestClient) -> None:
    response = await async_client.get(
        "/api/v1/schedule/8220DB000039?start_time=05%3A00%3A00&end_time=07%3A00%3A00&day=1"
    )
    assert response.status_code == 200
    schedules = response.json()
    assert len(schedules) == 2
    assert "route" in schedules[0]
    assert "stop_time" in schedules[0]
    assert "trip" in schedules[0]
    assert "is_added_exception" in schedules[0]
    assert schedules[0]["is_added_exception"] is False
    assert schedules[0]["route"]["long_name"] == "Monkstown Avenue - Harristown"


async def test_schedule_returns_400_when_start_equals_end(async_client: AsyncTestClient) -> None:
    response = await async_client.get(
        "/api/v1/schedule/8220DB000039?start_time=07%3A00%3A00&end_time=07%3A00%3A00&day=1"
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Start time cannot be equal to end time"


async def test_schedule_returns_400_when_window_exceeds_6_hours(async_client: AsyncTestClient) -> None:
    response = await async_client.get(
        "/api/v1/schedule/8220DB000039?start_time=07%3A00%3A00&end_time=16%3A00%3A00&day=1"
    )
    assert response.status_code == 400
    assert (
        response.json()["detail"]
        == "The difference of hours between start and end time must be at most 6 hours"
    )
