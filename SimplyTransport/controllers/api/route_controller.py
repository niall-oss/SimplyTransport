from typing import Annotated

from advanced_alchemy.exceptions import NotFoundError
from litestar import Controller, get
from litestar.di import NamedDependency, Provide
from litestar.exceptions import NotFoundException
from litestar.params import FromPath, QueryParameter
from SimplyTransport.api_contracts.route_contracts import Route, RouteWithTotal

from ...domain.route.route_repo import RouteRepo, provide_route_repo

__all__ = ["RouteController"]


class RouteController(Controller):
    dependencies = {
        "repo": Provide(provide_route_repo),
    }

    @get(
        "/",
        summary="All routes",
        description="Can be filtered by agency id",
        raises=[NotFoundException],
    )
    async def get_all_routes(
        self,
        repo: NamedDependency[RouteRepo],
        agency_id: Annotated[
            str | None,
            QueryParameter(name="agencyId", description="Optional: Agency ID to filter by"),
        ] = None,
    ) -> list[Route]:
        if agency_id:
            result = await repo.get_many(agency_id=agency_id)
            if not result or len(result) == 0:
                raise NotFoundException(detail=f"Routes not found with agency id {agency_id}")
        else:
            result = await repo.get_many()
        return [Route.model_validate(obj) for obj in result]

    @get(
        "/count",
        summary="All routes with total count",
        description="Can be filtered by agency id",
        raises=[NotFoundException],
    )
    async def get_all_routes_and_count(
        self,
        repo: NamedDependency[RouteRepo],
        agency_id: Annotated[
            str | None,
            QueryParameter(name="agencyId", description="Optional: Agency ID to filter by"),
        ] = None,
    ) -> RouteWithTotal:
        if agency_id:
            result, total = await repo.get_many_and_count(agency_id=agency_id)
            if not result or len(result) == 0:
                raise NotFoundException(detail=f"Routes not found with agency id {agency_id}")
        else:
            result, total = await repo.get_many_and_count()
        return RouteWithTotal(total=total, routes=[Route.model_validate(obj) for obj in result])

    @get("/{id:str}", summary="Route by ID", raises=[NotFoundException])
    async def get_route_by_id(self, repo: NamedDependency[RouteRepo], id: FromPath[str]) -> Route:
        try:
            result = await repo.get(id)
        except NotFoundError as e:
            raise NotFoundException(detail=f"Route not found with id {id}") from e
        return Route.model_validate(result)
