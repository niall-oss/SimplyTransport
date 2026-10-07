from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Literal, cast

from litestar.connection import ASGIConnection, Request
from litestar.datastructures import MutableScopeHeaders
from litestar.exceptions import NotAuthorizedException
from litestar.middleware._utils import should_bypass_middleware
from litestar.middleware.authentication import AbstractAuthenticationMiddleware, AuthenticationResult
from litestar.middleware.rate_limit import RateLimitConfig
from litestar.security.jwt import Token
from litestar.types import ASGIApp, Message, Receive, Scope, Send
from litestar.types.asgi_types import HTTPResponseStartEvent
from SimplyTransport.lib import settings

ANONYMOUS_SUBJECT = "anonymous"
JWT_ALGORITHM = "HS256"
_UNAUTHORIZED = "Missing or invalid access token"
AuthSource = Literal["bearer", "cookie"]


def issue_access_token() -> str:
    """Sign an anonymous JWT. Nothing about the caller is stored."""
    now = datetime.now(UTC)
    token = Token(
        sub=ANONYMOUS_SUBJECT,
        iat=now,
        exp=now + timedelta(seconds=settings.app.API_TOKEN_TTL_SECONDS),
    )
    return token.encode(secret=settings.app.SECRET_KEY, algorithm=JWT_ALGORITHM)


def decode_access_token(encoded_token: str) -> Token:
    """Verify a bearer token or site cookie. Rejects expired and foreign subjects."""
    try:
        token = Token.decode(
            encoded_token=encoded_token,
            secret=settings.app.SECRET_KEY,
            algorithm=JWT_ALGORITHM,
        )
    except NotAuthorizedException as exc:
        raise NotAuthorizedException(detail=_UNAUTHORIZED) from exc
    if token.sub != ANONYMOUS_SUBJECT:
        raise NotAuthorizedException(detail=_UNAUTHORIZED)
    return token


def access_token_is_valid(encoded_token: str | None) -> bool:
    if not encoded_token:
        return False
    try:
        decode_access_token(encoded_token)
    except NotAuthorizedException:
        return False
    return True


def cookie_header_value(encoded_token: str) -> str:
    """HttpOnly site cookie. Secure only in production, where the site is HTTPS."""
    parts = [
        f"{settings.app.API_TOKEN_COOKIE_NAME}={encoded_token}",
        "HttpOnly",
        "Path=/",
        "SameSite=Lax",
        f"Max-Age={settings.app.API_TOKEN_TTL_SECONDS}",
    ]
    if settings.app.ENVIRONMENT == "PROD":
        parts.append("Secure")
    return "; ".join(parts)


def _client_host(request: Request) -> str:
    client = request.client
    if client is None or not client.host:
        return "127.0.0.1"
    return client.host


def api_client_id(request: Request) -> str:
    """Separate Redis key from token minting. Litestar's limiter ignores the path."""
    return f"api:{_client_host(request)}"


def token_client_id(request: Request) -> str:
    return f"token:{_client_host(request)}"


def request_has_bearer_token(request: Request) -> bool:
    """Cookie calls are the website and rendered pages. They do not spend the bearer budget."""
    authorization = request.headers.get("authorization", "")
    return authorization.lower().startswith("bearer ")


def bearer_rate_limit_config() -> RateLimitConfig:
    return RateLimitConfig(
        rate_limit=("minute", settings.app.API_BEARER_RATE_LIMIT_PER_MINUTE),
        identifier_for_request=api_client_id,
        check_throttle_handler=request_has_bearer_token,
    )


def token_mint_rate_limit_config() -> RateLimitConfig:
    return RateLimitConfig(
        rate_limit=("hour", settings.app.API_TOKEN_MINT_LIMIT_PER_HOUR),
        identifier_for_request=token_client_id,
    )


def _append_set_cookie(message: HTTPResponseStartEvent, encoded_token: str) -> None:
    headers = MutableScopeHeaders(message)
    headers.headers.append((b"set-cookie", cookie_header_value(encoded_token).encode("latin-1")))


def _send_with_access_cookie(send: Send, encoded_token: str) -> Send:
    async def send_wrapper(message: Message) -> None:
        if message["type"] == "http.response.start":
            _append_set_cookie(cast(HTTPResponseStartEvent, message), encoded_token)
        await send(message)

    return send_wrapper


def _credentials_from_connection(connection: ASGIConnection) -> tuple[AuthSource, str]:
    authorization = connection.headers.get("authorization", "")
    if authorization:
        scheme, _, value = authorization.partition(" ")
        if scheme.lower() == "bearer" and value:
            return "bearer", value
        raise NotAuthorizedException(detail=_UNAUTHORIZED)
    cookie = connection.cookies.get(settings.app.API_TOKEN_COOKIE_NAME, "")
    if cookie:
        return "cookie", cookie
    raise NotAuthorizedException(detail=_UNAUTHORIZED)


class ApiTokenMiddleware(AbstractAuthenticationMiddleware):
    """Accept a bearer token or the site cookie on /api/v1.

    When the cookie authenticated the call, set a fresh cookie on the response.
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app=app)

    async def authenticate_request(self, connection: ASGIConnection) -> AuthenticationResult:
        _source, encoded = _credentials_from_connection(connection)
        return AuthenticationResult(user=ANONYMOUS_SUBJECT, auth=decode_access_token(encoded))

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if should_bypass_middleware(
            exclude_http_methods=self.exclude_http_methods,
            exclude_opt_key=self.exclude_opt_key,
            exclude_path_pattern=self.exclude,
            scope=scope,
            scopes=self.scopes,
        ):
            await self.app(scope, receive, send)
            return

        connection = ASGIConnection(scope)
        source, encoded = _credentials_from_connection(connection)
        token = decode_access_token(encoded)
        scope["user"] = ANONYMOUS_SUBJECT
        scope["auth"] = token
        if source == "cookie":
            send = _send_with_access_cookie(send, issue_access_token())
        await self.app(scope, receive, send)


class SiteAccessCookieMiddleware:
    """Set st_access_token on HTML responses when the browser does not already have a valid one."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        connection = ASGIConnection(scope)
        existing = connection.cookies.get(settings.app.API_TOKEN_COOKIE_NAME)
        if access_token_is_valid(existing):
            await self.app(scope, receive, send)
            return

        encoded_token = issue_access_token()

        async def send_html_cookie(message: Message) -> None:
            if message["type"] == "http.response.start":
                start = cast(HTTPResponseStartEvent, message)
                content_type = MutableScopeHeaders(start).get("content-type", "")
                if content_type.startswith("text/html"):
                    _append_set_cookie(start, encoded_token)
            await send(message)

        await self.app(scope, receive, send_html_cookie)
