from litestar import Controller, post
from litestar.status_codes import HTTP_200_OK
from pydantic import BaseModel
from SimplyTransport.lib import settings
from SimplyTransport.lib.auth import issue_access_token

__all__ = ["TokenController"]


class AccessTokenResponse(BaseModel):
    access_token: str
    token_type: str
    expires_in: int


class TokenController(Controller):
    @post("/token", summary="Issue an access token", status_code=HTTP_200_OK)
    async def issue_token(self) -> AccessTokenResponse:
        """Return a bearer token for /api/v1.

        Send access_token as Authorization Bearer. The token expires after expires_in seconds.
        Request a new one when it expires or the API returns 401.
        """
        return AccessTokenResponse(
            access_token=issue_access_token(),
            token_type="bearer",
            expires_in=settings.app.API_TOKEN_TTL_SECONDS,
        )
