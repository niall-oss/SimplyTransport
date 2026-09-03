import pytest
from litestar.testing import AsyncTestClient

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_agencies_list_returns_all_agencies(async_client: AsyncTestClient) -> None:
    response = await async_client.get("api/v1/agency/")
    assert response.status_code == 200
    agencies = response.json()
    assert len(agencies) == 7
    assert agencies[0]["id"] == "7778006"
    assert agencies[0]["name"] == "Go-Ahead Ireland"
    assert agencies[0]["url"] == "https://www.goaheadireland.ie/"
    assert agencies[0]["timezone"] == "Europe/London"
    assert agencies[0]["dataset"] == "TFI"


async def test_agencies_count_includes_total(async_client: AsyncTestClient) -> None:
    response = await async_client.get("api/v1/agency/count")
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == len(payload["agencies"]) == 7
    assert payload["agencies"][0]["id"] == "7778006"
    assert payload["agencies"][0]["name"] == "Go-Ahead Ireland"
    assert payload["agencies"][0]["url"] == "https://www.goaheadireland.ie/"
    assert payload["agencies"][0]["timezone"] == "Europe/London"
    assert payload["agencies"][0]["dataset"] == "TFI"


async def test_agency_returns_match_for_known_id(async_client: AsyncTestClient) -> None:
    response = await async_client.get("api/v1/agency/7778006")
    assert response.status_code == 200
    agency = response.json()
    assert agency["id"] == "7778006"
    assert agency["name"] == "Go-Ahead Ireland"
    assert agency["url"] == "https://www.goaheadireland.ie/"
    assert agency["timezone"] == "Europe/London"
    assert agency["dataset"] == "TFI"


async def test_agency_returns_404_for_unknown_id(async_client: AsyncTestClient) -> None:
    response = await async_client.get("api/v1/agency/7778007")
    assert response.status_code == 404
    assert response.json()["detail"] == "Agency not found with id 7778007"
