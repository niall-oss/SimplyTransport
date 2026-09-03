import pytest
from freezegun import freeze_time
from litestar.testing import AsyncTestClient

pytestmark = pytest.mark.asyncio(loop_scope="session")


@freeze_time("2025-03-21 12:00:00")
async def test_realtime_stop_page_renders_for_known_stop(async_client: AsyncTestClient) -> None:
    response = await async_client.get("/realtime/stop/RT_E2E_S1")
    assert response.status_code == 200
    html = response.text
    assert "Sorry this stop could not be found" not in html
    assert "Stop: Test 1" in html
    assert "/realtime/stop/RT_E2E_S1/realtime-table" in html


@freeze_time("2025-03-21 12:00:00")
async def test_realtime_stop_table_shows_removed_and_late_rows(async_client: AsyncTestClient) -> None:
    response = await async_client.get("/realtime/stop/RT_E2E_S1/realtime-table")
    assert response.status_code == 200
    html = response.text
    assert "realtime-row-removed" in html
    assert "Cancelled" in html
    assert "6 min" in html


async def test_realtime_stop_page_returns_not_found_for_unknown_stop(
    async_client: AsyncTestClient,
) -> None:
    response = await async_client.get("/realtime/stop/does-not-exist")
    assert "Sorry this stop could not be found" in response.text


async def test_realtime_route_page_renders_for_known_route(async_client: AsyncTestClient) -> None:
    response = await async_client.get("/realtime/route/3623_54684/0")
    assert response.status_code == 200
    assert "Route: 4" in response.text


async def test_realtime_trip_page_renders_for_known_trip(async_client: AsyncTestClient) -> None:
    response = await async_client.get("/realtime/trip/3623_8603")
    assert response.status_code == 200
    assert "Trip: 2616" in response.text
