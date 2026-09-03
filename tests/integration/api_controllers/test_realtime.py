import pytest
from litestar.testing import AsyncTestClient

pytestmark = pytest.mark.asyncio(loop_scope="session")

_REALTIME_WINDOW = "/api/v1/realtime/RT_E2E_S1?start_time=11%3A50%3A00&end_time=12%3A30%3A00&day=1"


async def test_realtime_schedule_returns_rows_for_stop_in_time_window(
    async_client: AsyncTestClient,
) -> None:
    response = await async_client.get(_REALTIME_WINDOW)
    assert response.status_code == 200
    rows = response.json()
    assert len(rows) >= 1
    late = next(row for row in rows if row["delay_in_seconds"] == 360)
    assert late["on_time_status"] == "LATE"
    assert late["is_trip_removed"] is False


async def test_realtime_schedule_returns_400_when_start_equals_end(async_client: AsyncTestClient) -> None:
    response = await async_client.get(
        "/api/v1/realtime/RT_E2E_S1?start_time=12%3A00%3A00&end_time=12%3A00%3A00&day=1"
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Start time cannot be equal to end time"


async def test_realtime_schedule_returns_400_when_window_exceeds_4_hours(
    async_client: AsyncTestClient,
) -> None:
    response = await async_client.get(
        "/api/v1/realtime/RT_E2E_S1?start_time=07%3A00%3A00&end_time=12%3A00%3A00&day=1"
    )
    assert response.status_code == 400
    assert (
        response.json()["detail"]
        == "The difference of hours between start and end time must be at most 4 hours"
    )
