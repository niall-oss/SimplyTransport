import pytest
from litestar.testing import AsyncTestClient

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_stop_times_return_rows_for_known_stop(async_client: AsyncTestClient) -> None:
    response = await async_client.get("api/v1/stoptime/stop/8240DB000324")
    assert response.status_code == 200
    stop_times = response.json()
    assert len(stop_times) == 1
    assert stop_times[0]["stop_id"] == "8240DB000324"


async def test_stop_times_return_404_for_unknown_stop(async_client: AsyncTestClient) -> None:
    response = await async_client.get("api/v1/stoptime/stop/does-not-exist")
    assert response.status_code == 404


async def test_stop_times_return_rows_for_known_trip(async_client: AsyncTestClient) -> None:
    response = await async_client.get("api/v1/stoptime/trip/3623_8603")
    assert response.status_code == 200
    stop_times = response.json()
    assert len(stop_times) == 56
    assert all(item["trip_id"] == "3623_8603" for item in stop_times)


async def test_stop_times_return_404_for_unknown_trip(async_client: AsyncTestClient) -> None:
    response = await async_client.get("api/v1/stoptime/trip/does-not-exist")
    assert response.status_code == 404
