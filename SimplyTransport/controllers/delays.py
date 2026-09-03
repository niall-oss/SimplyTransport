from litestar import Controller, get
from litestar.di import NamedDependency, Provide
from litestar.params import FromPath
from litestar.response import Template

from SimplyTransport.lib.cache_keys import CacheKeys, key_builder_from_path
from SimplyTransport.timescale.ts_stop_times.repo import TSStopTimeRepository, provide_ts_stop_time_repo

__all__ = [
    "DelaysController",
]


class DelaysController(Controller):
    dependencies = {"repo": Provide(provide_ts_stop_time_repo)}

    @get(
        "/route/{route_code:str}",
        cache=86400,
        cache_key_builder=key_builder_from_path(
            CacheKeys.Delays.DELAYS_HTML_ROUTE_KEY_TEMPLATE, "route_code"
        ),
    )
    async def delays_route(
        self,
        route_code: FromPath[str],
        repo: NamedDependency[TSStopTimeRepository],
    ) -> Template:
        result = await repo.get_aggregated_delay_on_stop_on_route_on_time(route_code=route_code)

        return Template(template_name="/delays/routes/route.html", context={"delay": result})
