from typing import Annotated

from advanced_alchemy.exceptions import NotFoundError
from advanced_alchemy.filters import LimitOffset
from litestar import Controller, get
from litestar.di import NamedDependency, Provide
from litestar.exceptions import NotFoundException
from litestar.pagination import OffsetPagination  # type: ignore
from litestar.params import FromPath, QueryParameter
from SimplyTransport.api_contracts.stop_contracts import Stop, StopDetailed
from SimplyTransport.lib.cache_keys import CacheKeys, key_builder_from_path

from ...domain.route.route_repo import RouteRepo, provide_route_repo
from ...domain.services.stop_detail_service import assemble_stop_detailed
from ...domain.stop.stop_repo import StopRepo, provide_stop_repo

__all__ = ["StopController"]

_STOP_DETAILED_CACHE_TTL_S = 86400


class StopController(Controller):
    dependencies = {
        "repo": Provide(provide_stop_repo),
        "route_repo": Provide(provide_route_repo),
    }

    @get(
        "/{id:str}/detailed",
        summary="Stop with routes and features",
        description="A stop with routes and features included.",
        raises=[NotFoundException],
        cache=_STOP_DETAILED_CACHE_TTL_S,
        cache_key_builder=key_builder_from_path(CacheKeys.StopApi.DETAILED_KEY_TEMPLATE, "id"),
    )
    async def get_stop_detailed_by_id(
        self,
        repo: NamedDependency[StopRepo],
        route_repo: NamedDependency[RouteRepo],
        id: FromPath[str],
    ) -> StopDetailed:
        try:
            return await assemble_stop_detailed(repo, route_repo, id)
        except NotFoundError as e:
            raise NotFoundException(detail=f"Stop not found with id {id}") from e

    @get("/{id:str}", summary="Stop by ID", raises=[NotFoundException])
    async def get_stop_by_id(self, repo: NamedDependency[StopRepo], id: FromPath[str]) -> Stop:
        try:
            result = await repo.get(id)
        except NotFoundError as e:
            raise NotFoundException(detail=f"Stop not found with id {id}") from e
        return Stop.model_validate(result)

    @get("/code/{code:str}", summary="Stop by code", raises=[NotFoundException])
    async def get_stop_by_code(self, repo: NamedDependency[StopRepo], code: FromPath[str]) -> Stop:
        try:
            result = await repo.get_by_code(code)
        except NotFoundError as e:
            raise NotFoundException(detail=f"Stop not found with code {code}") from e
        return Stop.model_validate(result)

    @get(
        "/search",
        summary="Search stops by name or code",
        description="Search is case insensitive",
        raises=[NotFoundException],
    )
    async def search_stops_by_name_or_code(
        self,
        repo: NamedDependency[StopRepo],
        limit_offset: NamedDependency[LimitOffset],
        search: Annotated[
            str,
            QueryParameter(name="search", description="Search string to search by name or code"),
        ],
    ) -> OffsetPagination[Stop]:
        try:
            results, total = await repo.list_by_name_or_code(search=search, limit_offset=limit_offset)
        except NotFoundError as e:
            raise NotFoundException(detail=f"Stops not found with name/code beginning with {search}") from e
        return OffsetPagination[Stop](
            total=total,
            items=[Stop.model_validate(obj) for obj in results],
            limit=limit_offset.limit,
            offset=limit_offset.offset,
        )
