import pytest
from litestar.testing import AsyncTestClient

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_calendar_dates_list_returns_all_dates(async_client: AsyncTestClient) -> None:
    response = await async_client.get("api/v1/calendardate/")
    assert response.status_code == 200
    dates = response.json()
    assert len(dates) == 238
    assert "service_id" in dates[0]


async def test_calendar_dates_count_includes_total(async_client: AsyncTestClient) -> None:
    response = await async_client.get("api/v1/calendardate/count")
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == len(payload["calendar_dates"]) == 238


async def test_calendar_dates_return_rows_for_known_service(async_client: AsyncTestClient) -> None:
    response = await async_client.get("api/v1/calendardate/154")
    assert response.status_code == 200
    dates = response.json()
    assert len(dates) == 3
    assert dates[0]["service_id"] == "154"
    assert dates[0]["exception_type"] == "removed"
    assert all(item["service_id"] == "154" for item in dates)


async def test_calendar_dates_return_404_for_unknown_service(async_client: AsyncTestClient) -> None:
    response = await async_client.get("api/v1/calendardate/does-not-exist")
    assert response.status_code == 404
    assert response.json()["detail"] == "CalendarDates not found with service_id does-not-exist"


async def test_calendar_dates_on_date_match_requested_day(async_client: AsyncTestClient) -> None:
    response = await async_client.get("api/v1/calendardate/date/2023-10-30")
    assert response.status_code == 200
    dates = response.json()
    assert len(dates) == 24
    assert all(item["date"] == "2023-10-30" for item in dates)
