from advanced_alchemy.exceptions import NotFoundError
from advanced_alchemy.filters import LimitOffset, OrderBy
from advanced_alchemy.repository import SQLAlchemyAsyncRepository
from litestar.di import NamedDependency
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from SimplyTransport.api_contract.map_payloads import RouteSummary
from SimplyTransport.domain.route.model import RouteModel
from SimplyTransport.lib.cache import RedisService

from ..stop_times.model import StopTimeModel
from ..trip.model import TripModel


class RouteRepository(SQLAlchemyAsyncRepository[RouteModel]):  # type: ignore
    """Route repository."""

    model_type = RouteModel
    cache: RedisService

    def __init__(self, session: AsyncSession, *, cache: RedisService):
        self.cache = cache
        super().__init__(session=session)

    async def list_by_short_name_or_long_name(
        self, search: str, limit_offset: LimitOffset
    ) -> tuple[list[RouteModel], int]:
        """List stops that start with name/code."""

        results, total = await self.get_many_and_count(
            RouteModel.short_name.istartswith(search) | RouteModel.long_name.istartswith(search),
            limit_offset,
            OrderBy(RouteModel.short_name, "asc"),  # type: ignore
        )

        if total == 0:
            raise NotFoundError()

        return results, total

    async def get_routes_by_stop_id(self, stop_id: str) -> list[RouteModel]:
        """Get routes by stop_id."""

        return await self.get_many(
            RouteModel.trips.any(TripModel.stop_times.any(StopTimeModel.stop_id == stop_id))
        )

    async def get_routes_by_stop_ids(self, stop_ids: set[str]) -> dict[str, list[RouteSummary]]:
        """Routes per stop; ``stop_ids`` must be deduplicated (use a set at call sites)."""

        if not stop_ids:
            return {}

        stmt = (
            select(
                StopTimeModel.stop_id,
                RouteModel.id,
                RouteModel.short_name,
                RouteModel.long_name,
            )
            .select_from(StopTimeModel)
            .join(TripModel, StopTimeModel.trip_id == TripModel.id)
            .join(RouteModel, TripModel.route_id == RouteModel.id)
            .where(StopTimeModel.stop_id.in_(stop_ids))
            .distinct()
        )
        result = await self.session.execute(stmt)
        rows = result.all()

        by_stop: dict[str, dict[str, RouteSummary]] = {sid: {} for sid in stop_ids}
        for stop_id, route_id, short_name, long_name in rows:
            summary = RouteSummary(route_id=route_id, short_name=short_name, long_name=long_name)
            by_stop[stop_id].setdefault(route_id, summary)

        return {sid: list(by_stop[sid].values()) for sid in stop_ids}

    async def get_routes_by_stop_id_with_agency(self, stop_id: str) -> list[RouteModel]:
        """Get routes by stop_id with agency."""

        return await self.get_many(
            RouteModel.trips.any(TripModel.stop_times.any(StopTimeModel.stop_id == stop_id)),
            statement=select(RouteModel).options(joinedload(RouteModel.agency)),
        )

    async def get_by_id_with_agency(self, id: str) -> RouteModel:
        """Get a route by id with agency."""

        return await self.get(id, statement=select(RouteModel).options(joinedload(RouteModel.agency)))

    async def get_with_agencies(self) -> list[RouteModel]:
        """Get all routes with agencies"""

        return await self.get_many(statement=select(RouteModel).options(joinedload(RouteModel.agency)))

    async def get_with_agencies_by_agency_id(self, agency_id: str) -> list[RouteModel]:
        """Get all routes with agencies by agency_id"""

        return await self.get_many(
            RouteModel.agency_id == agency_id,
            statement=select(RouteModel).options(joinedload(RouteModel.agency)),
        )


async def provide_route_repo(
    db_session: NamedDependency[AsyncSession], redis_service: NamedDependency[RedisService]
) -> RouteRepository:
    """This provides the Route repository."""

    return RouteRepository(session=db_session, cache=redis_service)
