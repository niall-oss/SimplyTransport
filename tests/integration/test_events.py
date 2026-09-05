import pytest
from litestar.testing import AsyncTestClient
from SimplyTransport.controllers.events_controller import ALL_EVENTS
from SimplyTransport.domain.events.event_types import EventType

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_events_page_explains_what_events_are(async_client: AsyncTestClient) -> None:
    response = await async_client.get("events")
    assert response.status_code == 200
    assert "Events are records of things that have happened in the system" in response.text


async def test_events_page_includes_pagesize_options(async_client: AsyncTestClient) -> None:
    response = await async_client.get("events")
    assert response.status_code == 200
    html = response.text
    assert '<select class="dropdown" name="pageSize">' in html
    assert '<option value="10">PageSize : 10</option>' in html
    assert '<option value="20">20</option>' in html
    assert '<option value="50">50</option>' in html
    assert '<option value="100">100</option>' in html


async def test_events_page_lists_all_event_types(async_client: AsyncTestClient) -> None:
    response = await async_client.get("events")
    assert response.status_code == 200
    html = response.text
    assert f'<option value="{ALL_EVENTS}">{ALL_EVENTS}</option>' in html
    for event_type in EventType:
        assert f'<option value="{event_type.value}">{event_type.value}</option>' in html


async def test_event_search_defaults_to_all_types_descending(async_client: AsyncTestClient) -> None:
    response = await async_client.get("events/search")
    assert response.status_code == 200
    html = response.text
    assert "Limit: 20" in html
    assert f'<span class="event-chip">{ALL_EVENTS}</span>' in html
    assert '<span class="event-chip">desc</span>' in html


async def test_event_search_applies_sort_and_type(async_client: AsyncTestClient) -> None:
    response = await async_client.get("events/search?sort=asc&search_type=gtfs.database.updated")
    assert response.status_code == 200
    html = response.text
    assert f'<span class="event-chip">{EventType.GTFS_DATABASE_UPDATED.value}</span>' in html
    assert '<span class="event-chip">asc</span>' in html


async def test_event_search_returns_400_for_invalid_type(async_client: AsyncTestClient) -> None:
    response = await async_client.get("events/search?search_type=invalid")
    assert response.status_code == 400
