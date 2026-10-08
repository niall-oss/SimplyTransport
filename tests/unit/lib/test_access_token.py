from datetime import UTC, datetime, timedelta

import jwt
import pytest
from litestar import Litestar, Router, get
from litestar.exceptions import NotAuthorizedException
from litestar.stores.memory import MemoryStore
from litestar.stores.registry import StoreRegistry
from litestar.testing import AsyncTestClient
from pydantic import ValidationError
from SimplyTransport.controllers.api.token_controller import TokenController
from SimplyTransport.lib import settings
from SimplyTransport.lib.auth import (
    ApiTokenMiddleware,
    access_cookie_needs_renewal,
    bearer_rate_limit_config,
    cookie_header_value,
    decode_access_token,
    issue_access_token,
    token_mint_rate_limit_config,
)
from SimplyTransport.lib.settings import AppSettings, reset_settings


def test_access_token_round_trip() -> None:
    token = decode_access_token(issue_access_token())
    assert token.sub == "anonymous"
    assert token.exp > datetime.now(UTC)


def test_expired_token_is_rejected() -> None:
    now = datetime.now(UTC)
    encoded = jwt.encode(
        {
            "sub": "anonymous",
            "iat": int((now - timedelta(hours=2)).timestamp()),
            "exp": int((now - timedelta(minutes=1)).timestamp()),
        },
        settings.app.SECRET_KEY,
        algorithm="HS256",
    )
    with pytest.raises(NotAuthorizedException):
        decode_access_token(encoded)


def test_foreign_subject_is_rejected() -> None:
    now = datetime.now(UTC)
    encoded = jwt.encode(
        {
            "sub": "someone",
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=5)).timestamp()),
        },
        settings.app.SECRET_KEY,
        algorithm="HS256",
    )
    with pytest.raises(NotAuthorizedException):
        decode_access_token(encoded)


def test_cookie_header_is_httponly() -> None:
    header = cookie_header_value("abc.def.ghi")
    assert header.startswith(f"{settings.app.API_TOKEN_COOKIE_NAME}=abc.def.ghi;")
    assert "HttpOnly" in header
    assert "Path=/" in header
    assert "SameSite=Lax" in header
    assert "Max-Age=" in header
    if settings.app.ENVIRONMENT == "PROD":
        assert "Secure" in header
    else:
        assert "Secure" not in header


def test_token_defaults() -> None:
    assert AppSettings.model_fields["API_TOKEN_TTL_SECONDS"].default == 3600
    assert AppSettings.model_fields["API_TOKEN_COOKIE_NAME"].default == "st_access_token"
    assert AppSettings.model_fields["API_TOKEN_MINT_LIMIT_PER_HOUR"].default == 10
    assert AppSettings.model_fields["API_BEARER_RATE_LIMIT_PER_MINUTE"].default == 60


@pytest.mark.parametrize("ttl", [0, -1])
def test_nonpositive_token_ttl_is_rejected(monkeypatch: pytest.MonkeyPatch, ttl: int) -> None:
    monkeypatch.setenv("API_TOKEN_TTL_SECONDS", str(ttl))
    reset_settings()
    try:
        with pytest.raises(ValidationError):
            settings.get_settings()
    finally:
        reset_settings()


def test_cookie_near_expiry_needs_renewal() -> None:
    now = datetime.now(UTC)
    expiring = jwt.encode(
        {
            "sub": "anonymous",
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(seconds=60)).timestamp()),
        },
        settings.app.SECRET_KEY,
        algorithm="HS256",
    )
    assert access_cookie_needs_renewal(expiring) is True
    assert access_cookie_needs_renewal(issue_access_token()) is False
    assert access_cookie_needs_renewal(None) is True


def test_production_rejects_default_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "PROD")
    monkeypatch.setenv("SECRET_KEY", "secret")
    reset_settings()
    try:
        with pytest.raises(ValidationError):
            settings.get_settings()
    finally:
        reset_settings()


def test_production_rejects_short_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "PROD")
    monkeypatch.setenv("SECRET_KEY", "x" * 31)
    reset_settings()
    try:
        with pytest.raises(ValidationError):
            settings.get_settings()
    finally:
        reset_settings()


def test_production_accepts_long_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "PROD")
    monkeypatch.setenv("SECRET_KEY", "x" * 32)
    reset_settings()
    try:
        loaded = settings.get_settings()
        assert loaded.SECRET_KEY == "x" * 32
        assert "Secure" in cookie_header_value("abc")
    finally:
        reset_settings()


def _memory_store(_name: str) -> MemoryStore:
    return MemoryStore()


@get("/ping")
async def ping() -> dict[str, bool]:
    return {"ok": True}


@pytest.mark.asyncio
async def test_bearer_limit_does_not_count_cookies(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("API_BEARER_RATE_LIMIT_PER_MINUTE", "2")
    reset_settings()
    try:
        app = Litestar(
            route_handlers=[
                Router(
                    path="/",
                    middleware=[ApiTokenMiddleware, bearer_rate_limit_config().middleware],
                    route_handlers=[ping],
                )
            ],
            stores=StoreRegistry(default_factory=_memory_store),
        )
        async with AsyncTestClient(app=app) as client:
            headers = {"Authorization": f"Bearer {issue_access_token()}"}
            assert (await client.get("/ping", headers=headers)).status_code == 200
            assert (await client.get("/ping", headers=headers)).status_code == 200
            assert (await client.get("/ping", headers=headers)).status_code == 429

            cookies_token = issue_access_token()
            client.cookies.set(settings.app.API_TOKEN_COOKIE_NAME, cookies_token)
            for _ in range(4):
                response = await client.get("/ping")
                assert response.status_code == 200
    finally:
        reset_settings()


@pytest.mark.asyncio
async def test_token_mint_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("API_TOKEN_MINT_LIMIT_PER_HOUR", "2")
    reset_settings()
    try:
        app = Litestar(
            route_handlers=[
                Router(
                    path="/api/v1",
                    middleware=[token_mint_rate_limit_config().middleware],
                    route_handlers=[TokenController],
                )
            ],
            stores=StoreRegistry(default_factory=_memory_store),
        )
        async with AsyncTestClient(app=app) as client:
            assert (await client.post("/api/v1/token")).status_code == 200
            assert (await client.post("/api/v1/token")).status_code == 200
            assert (await client.post("/api/v1/token")).status_code == 429
    finally:
        reset_settings()
