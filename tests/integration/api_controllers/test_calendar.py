import pytest
from litestar.testing import AsyncTestClient

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_calendars_list_returns_all_calendars(async_client: AsyncTestClient) -> None:
    response = await async_client.get("api/v1/calendar/")
    assert response.status_code == 200
    calendars = response.json()
    assert len(calendars) == 117
    assert calendars[0]["id"] == "27"
    assert calendars[0]["monday"] == 0
    assert calendars[0]["tuesday"] == 0
    assert calendars[0]["wednesday"] == 0
    assert calendars[0]["thursday"] == 0
    assert calendars[0]["friday"] == 0
    assert calendars[0]["saturday"] == 0
    assert calendars[0]["sunday"] == 0
    assert calendars[0]["start_date"] == "2023-11-24"
    assert calendars[0]["end_date"] == "2099-11-24"
    assert calendars[0]["dataset"] == "TFI"


async def test_calendars_count_includes_total(async_client: AsyncTestClient) -> None:
    response = await async_client.get("api/v1/calendar/count")
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == len(payload["calendars"]) == 117
    assert payload["calendars"][0]["id"] == "27"
    assert payload["calendars"][0]["monday"] == 0
    assert payload["calendars"][0]["tuesday"] == 0
    assert payload["calendars"][0]["wednesday"] == 0
    assert payload["calendars"][0]["thursday"] == 0
    assert payload["calendars"][0]["friday"] == 0
    assert payload["calendars"][0]["saturday"] == 0
    assert payload["calendars"][0]["sunday"] == 0
    assert payload["calendars"][0]["start_date"] == "2023-11-24"
    assert payload["calendars"][0]["end_date"] == "2099-11-24"
    assert payload["calendars"][0]["dataset"] == "TFI"


async def test_calendar_returns_match_for_known_id(async_client: AsyncTestClient) -> None:
    response = await async_client.get("api/v1/calendar/27")
    assert response.status_code == 200
    calendar = response.json()
    assert calendar["id"] == "27"
    assert calendar["monday"] == 0
    assert calendar["tuesday"] == 0
    assert calendar["wednesday"] == 0
    assert calendar["thursday"] == 0
    assert calendar["friday"] == 0
    assert calendar["saturday"] == 0
    assert calendar["sunday"] == 0
    assert calendar["start_date"] == "2023-11-24"
    assert calendar["end_date"] == "2099-11-24"
    assert calendar["dataset"] == "TFI"


async def test_calendar_returns_404_for_unknown_id(async_client: AsyncTestClient) -> None:
    response = await async_client.get("api/v1/calendar/does-not-exist")
    assert response.status_code == 404
    assert response.json()["detail"] == "Calendar not found with id does-not-exist"


async def test_calendars_active_on_date_are_within_range(async_client: AsyncTestClient) -> None:
    response = await async_client.get("api/v1/calendar/date/2023-11-24")
    assert response.status_code == 200
    calendars = response.json()
    assert len(calendars) == 104
    assert calendars[0]["id"] == "27"
    assert calendars[0]["monday"] == 0
    assert calendars[0]["tuesday"] == 0
    assert calendars[0]["wednesday"] == 0
    assert calendars[0]["thursday"] == 0
    assert calendars[0]["friday"] == 0
    assert calendars[0]["saturday"] == 0
    assert calendars[0]["sunday"] == 0
    assert calendars[0]["start_date"] == "2023-11-24"
    assert calendars[0]["end_date"] == "2099-11-24"
    assert calendars[0]["dataset"] == "TFI"
    for calendar in calendars:
        assert calendar["start_date"] <= "2023-11-24" <= calendar["end_date"]
