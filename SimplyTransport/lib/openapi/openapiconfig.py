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

from .. import settings
from .tags import Tags

DESCRIPTION = """
Irish public transport data: GTFS tables, live arrivals, schedules, maps, delays, and statistics.
"""

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
        tags=Tags().list_all_tags(),
    )
