import math
from typing import Annotated

from advanced_alchemy.exceptions import NotFoundError
from advanced_alchemy.filters import LimitOffset
from litestar import Controller, get
from litestar.di import NamedDependency, Provide
from litestar.params import QueryParameter
from litestar.response import Template

from ..domain.route.repo import RouteRepository, provide_route_repo
from ..domain.stop.repo import StopRepository, provide_stop_repo
from ..lib.parameters.pagination_page_numbers import generate_pagination_pages

__all__ = [
    "SearchController",
]


class SearchController(Controller):
    dependencies = {
        "stop_repo": Provide(provide_stop_repo),
        "route_repo": Provide(provide_route_repo),
    }

    @get("/stops")
    async def stops(
        self,
        stop_repo: NamedDependency[StopRepository],
        limit_offset: NamedDependency[LimitOffset],
        search: Annotated[
            str,
            QueryParameter(name="search", description="Search string to search by name or code"),
        ],
    ) -> Template:
        try:
            stops, total = await stop_repo.list_by_name_or_code(search=search, limit_offset=limit_offset)
        except NotFoundError:
            stops = []
            total = 0

        current_page = limit_offset.offset // limit_offset.limit + 1
        total_pages = math.ceil(total / limit_offset.limit)
        pages = generate_pagination_pages(current_page, total_pages)

        return Template(
            "gtfs_search/stop_result.html",
            context={
                "stops": stops,
                "total": total,
                "search": search,
                "limit": limit_offset.limit,
                "current_page": current_page,
                "total_pages": total_pages,
                "pages": pages,
            },
        )

    @get("/stops/nearby")
    async def stops_nearby(
        self,
        latitude: Annotated[float, QueryParameter(name="latitude", description="Latitude of the user")],
        longitude: Annotated[float, QueryParameter(name="longitude", description="Longitude of the user")],
    ) -> Template:
        return Template(
            "gtfs_search/stop_nearby.html",
            context={
                "latitude": latitude,
                "longitude": longitude,
            },
        )

    @get("/routes")
    async def routes(
        self,
        route_repo: NamedDependency[RouteRepository],
        limit_offset: NamedDependency[LimitOffset],
        search: Annotated[
            str,
            QueryParameter(name="search", description="Search string to search by name or code"),
        ],
    ) -> Template:
        try:
            routes, total = await route_repo.list_by_short_name_or_long_name(
                search=search, limit_offset=limit_offset
            )
        except NotFoundError:
            routes = []
            total = 0

        current_page = limit_offset.offset // limit_offset.limit + 1
        total_pages = math.ceil(total / limit_offset.limit)
        pages = generate_pagination_pages(current_page, total_pages)

        return Template(
            "gtfs_search/route_result.html",
            context={
                "routes": routes,
                "total": total,
                "search": search,
                "limit": limit_offset.limit,
                "current_page": current_page,
                "total_pages": total_pages,
                "pages": pages,
            },
        )
