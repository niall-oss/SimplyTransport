from collections.abc import Sequence

from advanced_alchemy.repository import SQLAlchemyAsyncRepository
from litestar.di import NamedDependency
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from ...agency.model import AgencyModel
from ...route.model import RouteModel
from ...trip.model import TripModel
from ..enums import REMOVED_TRIP_RELATIONSHIPS
from ..trip.model import RTTripModel
from .model import RTVehicleModel


class RTVehicleRepository(SQLAlchemyAsyncRepository[RTVehicleModel]):  # type: ignore
    """RTVehicle repository."""

    async def get_vehicles_on_routes(
        self,
        route_ids: list,
        direction: int,
        *,
        exclude_removed_trips: bool = True,
    ) -> Sequence[RTVehicleModel]:
        """Get most recent vehicle updates for vehicles on routes.

        Args:
            route_ids (list): List of route IDs.
            direction (int): Trip direction.
            exclude_removed_trips: When True, omit vehicles whose latest ``rt_trip`` row marks the
                trip as CANCELED or DELETED (positions are still ingested for other uses).

        Returns:
            list: List of RTVehicleModel objects representing the most recent vehicle updates
            for vehicles on the specified routes.
        """

        subquery = (
            select(
                RTVehicleModel.vehicle_id,
                func.max(RTVehicleModel.time_of_update).label("max_time_of_update"),
            )
            .join(TripModel, TripModel.id == RTVehicleModel.trip_id)
            .where(TripModel.route_id.in_(route_ids))
            .where(TripModel.direction == direction)
            .group_by(RTVehicleModel.vehicle_id)
            .alias("subquery")
        )

        statement = (
            select(RTVehicleModel)
            .options(
                joinedload(RTVehicleModel.trip).joinedload(TripModel.route).joinedload(RouteModel.agency)
            )
            .join(TripModel, TripModel.id == RTVehicleModel.trip_id)
            .join(RouteModel, RouteModel.id == TripModel.route_id)
            .join(AgencyModel, RouteModel.agency_id == AgencyModel.id)
            .join(
                subquery,
                (subquery.c.vehicle_id == RTVehicleModel.vehicle_id)
                & (subquery.c.max_time_of_update == RTVehicleModel.time_of_update),
            )
            .where(TripModel.route_id.in_(route_ids))
            .where(TripModel.direction == direction)
            .order_by(RTVehicleModel.vehicle_id.desc())
        )

        if exclude_removed_trips:
            statement = statement.outerjoin(
                RTTripModel,
                (RTTripModel.trip_id == TripModel.id) & (RTTripModel.dataset == TripModel.dataset),
            ).where(
                or_(
                    RTTripModel.id.is_(None),
                    RTTripModel.schedule_relationship.not_in(list(REMOVED_TRIP_RELATIONSHIPS)),
                )
            )

        result = await self.session.execute(statement)
        return result.scalars().all()

    model_type = RTVehicleModel


async def provide_rt_vehicle_repo(db_session: NamedDependency[AsyncSession]) -> RTVehicleRepository:
    """This provides the RTVehicle repository."""

    return RTVehicleRepository(session=db_session)
