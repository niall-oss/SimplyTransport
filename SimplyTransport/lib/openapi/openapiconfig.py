from litestar.openapi import OpenAPIConfig
from litestar.openapi.plugins import (
    JsonRenderPlugin,
    RapidocRenderPlugin,
    RedocRenderPlugin,
    ScalarRenderPlugin,
    StoplightRenderPlugin,
    SwaggerRenderPlugin,
    YamlRenderPlugin,
)
from litestar.openapi.spec import Components, SecurityScheme

from .. import settings
from .tags import Tags

DESCRIPTION = """
Irish public transport data: GTFS tables, live arrivals, schedules, maps, delays, and statistics.

Routes under /api/v1 require an access token. POST /api/v1/token returns one.
Send access_token as Authorization Bearer. The token expires after expires_in seconds, one hour by default.
Request a new token when it expires, or when a call returns 401.
""".strip()

BEARER_SCHEME_DESCRIPTION = (
    "JWT from POST /api/v1/token. Send it as Authorization Bearer. "
    "Request a new token after expires_in seconds, or when the API returns 401."
)

favicon = "<link rel='icon' type='image/png' href='/favicon.ico'>"
render_plugins = [
    ScalarRenderPlugin(favicon=favicon),
    StoplightRenderPlugin(favicon=favicon),
    YamlRenderPlugin(favicon=favicon),
    JsonRenderPlugin(favicon=favicon),
    RapidocRenderPlugin(favicon=favicon),
    RedocRenderPlugin(favicon=favicon),
    SwaggerRenderPlugin(favicon=favicon),
]


def custom_open_api_config() -> OpenAPIConfig:
    return OpenAPIConfig(
        title=settings.app.NAME,
        version=settings.app.VERSION,
        path="/docs",
        render_plugins=render_plugins,
        create_examples=False,
        description=DESCRIPTION,
        use_handler_docstrings=True,
        tags=Tags().list_all_tags(),
        components=Components(
            security_schemes={
                "BearerToken": SecurityScheme(
                    type="http",
                    scheme="bearer",
                    bearer_format="JWT",
                    description=BEARER_SCHEME_DESCRIPTION,
                )
            }
        ),
    )
