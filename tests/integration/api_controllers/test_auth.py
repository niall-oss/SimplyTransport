from datetime import UTC, datetime, timedelta

import jwt
import pytest
from litestar.testing import AsyncTestClient
from SimplyTransport.lib import settings
from SimplyTransport.lib.auth import decode_access_token, issue_access_token

pytestmark = pytest.mark.asyncio(loop_scope="session")


def _set_cookie_value(header: str) -> str:
    prefix = f"{settings.app.API_TOKEN_COOKIE_NAME}="
    assert prefix in header
    raw = header.split(prefix, 1)[1]
    return raw.split(";", 1)[0]


async def test_api_rejects_missing_token(async_client: AsyncTestClient) -> None:
    saved_headers = dict(async_client.headers)
    saved_cookies = dict(async_client.cookies)
    async_client.headers.clear()
    async_client.cookies.clear()
    try:
        response = await async_client.get("/api/v1/agency/")
        assert response.status_code == 401
    finally:
        async_client.headers.clear()
        async_client.headers.update(saved_headers)
        async_client.cookies.update(saved_cookies)


async def test_bearer_token_allows_api_and_does_not_set_cookie(async_client: AsyncTestClient) -> None:
    response = await async_client.get("/api/v1/agency/")
    assert response.status_code == 200
    assert settings.app.API_TOKEN_COOKIE_NAME not in response.headers.get("set-cookie", "")


async def test_cookie_allows_api_and_slides(async_client: AsyncTestClient) -> None:
    saved_headers = dict(async_client.headers)
    saved_cookies = dict(async_client.cookies)
    async_client.headers.clear()
    async_client.cookies.clear()
    async_client.cookies.set(settings.app.API_TOKEN_COOKIE_NAME, issue_access_token())
    try:
        response = await async_client.get("/api/v1/agency/")
        assert response.status_code == 200
        refreshed = decode_access_token(_set_cookie_value(response.headers["set-cookie"]))
        assert refreshed.sub == "anonymous"
    finally:
        async_client.headers.clear()
        async_client.headers.update(saved_headers)
        async_client.cookies.clear()
        async_client.cookies.update(saved_cookies)


async def test_expired_bearer_token_is_rejected(async_client: AsyncTestClient) -> None:
    now = datetime.now(UTC)
    expired = jwt.encode(
        {
            "sub": "anonymous",
            "iat": int((now - timedelta(hours=2)).timestamp()),
            "exp": int((now - timedelta(minutes=1)).timestamp()),
        },
        settings.app.SECRET_KEY,
        algorithm="HS256",
    )
    response = await async_client.get("/api/v1/agency/", headers={"Authorization": f"Bearer {expired}"})
    assert response.status_code == 401


async def test_token_route_returns_bearer_token(async_client: AsyncTestClient) -> None:
    response = await async_client.post("/api/v1/token")
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == settings.app.API_TOKEN_TTL_SECONDS
    assert decode_access_token(body["access_token"]).sub == "anonymous"


async def test_map_page_sets_access_cookie(async_client: AsyncTestClient) -> None:
    cookie_name = settings.app.API_TOKEN_COOKIE_NAME
    async_client.cookies.delete(cookie_name)
    first = await async_client.get("/maps/agency/route/All")
    assert first.status_code == 200
    set_cookie = first.headers.get("set-cookie", "")
    assert cookie_name in set_cookie
    assert "HttpOnly" in set_cookie
    assert "SameSite=Lax" in set_cookie or "SameSite=lax" in set_cookie

    second = await async_client.get("/maps/agency/route/All")
    assert second.status_code == 200
    assert cookie_name not in second.headers.get("set-cookie", "")


async def test_openapi_describes_token_auth(async_client: AsyncTestClient) -> None:
    response = await async_client.get("/docs/openapi.json")
    assert response.status_code == 200
    spec = response.json()
    assert "POST /api/v1/token" in spec["info"]["description"]
    scheme = spec["components"]["securitySchemes"]["BearerToken"]
    assert scheme["type"] == "http"
    assert scheme["scheme"] == "bearer"
    assert "POST /api/v1/token" in scheme["description"]

    token_operation = spec["paths"]["/api/v1/token"]["post"]
    assert "401" in token_operation["description"]
    assert {"BearerToken": []} not in (token_operation.get("security") or [])

    agency_paths = [path for path in spec["paths"] if path.rstrip("/") == "/api/v1/agency"]
    assert agency_paths
    agency_operation = spec["paths"][agency_paths[0]]["get"]
    assert {"BearerToken": []} in agency_operation["security"]
    assert any(tag["name"] == "Auth" for tag in spec["tags"])
