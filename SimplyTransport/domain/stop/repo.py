from advanced_alchemy.exceptions import NotFoundError
from advanced_alchemy.filters import LimitOffset, OrderBy
from advanced_alchemy.repository import SQLAlchemyAsyncRepository
from litestar.di import NamedDependency
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from ...lib.distance_calculator import calculate_min_max_coordinates, distance_between_points
from ..route.model import RouteModel
from ..stop_features.model import StopFeatureModel
from ..stop_times.model import StopTimeModel
from ..trip.model import TripModel
from .model import StopModel


class StopRepository(SQLAlchemyAsyncRepository[StopModel]):  # type: ignore[type-var]
    """Stop repository."""

    model_type = StopModel

    async def get_by_code(self, code: str) -> StopModel:
        """Get a stop by code."""

        return await self.get_one(code=code)

    async def list_by_name_or_code(
        self, search: str, limit_offset: LimitOffset
    ) -> tuple[list[StopModel], int]:
        """List stops that start with name/code."""

        results, total = await self.get_many_and_count(
            StopModel.name.istartswith(search) | StopModel.code.istartswith(search),
            limit_offset,
            OrderBy(StopModel.code, "asc"),  # type: ignore
        )

        if total == 0:
            raise NotFoundError()

        return results, total

    async def get_stops_by_route_id(self, route_id: str, direction: int) -> list[StopModel]:
        """Get stops by route_id."""

        return await self.get_many(
            statement=select(StopModel)
            .join(StopTimeModel, StopTimeModel.stop_id == StopModel.id)
            .join(TripModel, TripModel.id == StopTimeModel.trip_id)
            .where(TripModel.direction == direction)
            .where(TripModel.route_id == route_id)
            .distinct(StopModel.id)
        )

    async def get_stops_by_route_ids(self, route_ids: list[str], direction: int) -> list[StopModel]:
        """Get stops by route_ids."""

        return await self.get_many(
            statement=select(StopModel)
            .join(StopTimeModel, StopTimeModel.stop_id == StopModel.id)
            .join(TripModel, TripModel.id == StopTimeModel.trip_id)
            .where(TripModel.direction == direction)
            .where(TripModel.route_id.in_(route_ids))
            .distinct(StopModel.id)
        )

    async def get_direction_of_stop(self, stop_id: str) -> int:
        """Get the direction of a stop."""

        result = await self._execute(
            statement=select(TripModel.direction)
            .join(StopTimeModel, StopTimeModel.trip_id == TripModel.id)
            .where(StopTimeModel.stop_id == stop_id)
            .limit(1)
        )
        return result.scalar() or 0

    async def get_by_route_id_with_sequence(
        self, route_id: str, direction: int
    ) -> list[tuple[StopModel, int]]:
        """Get stops by route_id with a stop_sequence."""

        result = await self.session.execute(
            statement=select(StopModel, StopTimeModel.stop_sequence)
            .join(StopTimeModel, StopTimeModel.stop_id == StopModel.id)
            .join(TripModel, TripModel.id == StopTimeModel.trip_id)
            .join(RouteModel, RouteModel.id == TripModel.route_id)
            .where(TripModel.direction == direction)
            .where(RouteModel.id == route_id)
            .group_by(StopModel.id, StopTimeModel.stop_sequence)
            .order_by(StopTimeModel.stop_sequence)
        )

        return [(row.StopModel, row.stop_sequence) for row in result.all()]

    async def get_by_id_with_stop_feature(self, id: str) -> StopModel:
        """Get a stop by id with stop feature."""

        return await self.get(id, statement=select(StopModel).options(joinedload(StopModel.stop_feature)))

    async def get_all_with_stop_feature(self) -> list[StopModel]:
        """Get all stops with stop features."""

        return await self.get_many(statement=select(StopModel))

    async def get_stops_with_realtime_displays(self) -> list[StopModel]:
        """Get stops by realtime displays."""

        return await self.get_many(
            statement=select(StopModel)
            .join(StopFeatureModel, StopFeatureModel.stop_id == StopModel.id)
            .where(StopFeatureModel.rtpi_active == True)  # noqa: E712
        )

    async def get_stops_with_shelters(self) -> list[StopModel]:
        """Get stops by realtime displays."""

        return await self.get_many(
            statement=select(StopModel)
            .join(StopFeatureModel, StopFeatureModel.stop_id == StopModel.id)
            .where(StopFeatureModel.shelter_active == True)  # noqa: E712
        )

    async def get_stops_that_are_unsurveyed(self) -> list[StopModel]:
        """Get stops by realtime displays."""

        return await self.get_many(
            statement=select(StopModel)
            .join(StopFeatureModel, StopFeatureModel.stop_id == StopModel.id)
            .where(StopFeatureModel.surveyed == False)  # noqa: E712
        )

    async def get_stops_near_location(
        self, latitude: float, longitude: float, distance_in_meters: int
    ) -> list[StopModel]:
        """Get stops near a location."""
        min_max_coordinates = calculate_min_max_coordinates(latitude, longitude, distance_in_meters)

        potential_stops = await self.get_many(
            statement=select(StopModel)
            .where(StopModel.lat.between(min_max_coordinates.min_latitude, min_max_coordinates.max_latitude))
            .where(
                StopModel.lon.between(min_max_coordinates.min_longitude, min_max_coordinates.max_longitude)
            )
            .where(StopModel.lat.is_not(None))
            .where(StopModel.lon.is_not(None))
        )
        # Database will return a square shape, so we need to filter out stops that are not within the circle
        stops = [
            stop
            for stop in potential_stops
            if distance_between_points(latitude, longitude, stop.lat, stop.lon) <= distance_in_meters  # type: ignore
        ]

        return stops


async def provide_stop_repo(db_session: NamedDependency[AsyncSession]) -> StopRepository:
    """This provides the Stop repository."""

    return StopRepository(session=db_session)
