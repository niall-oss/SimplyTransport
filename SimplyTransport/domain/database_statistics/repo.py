from datetime import date

from advanced_alchemy.repository import SQLAlchemyAsyncRepository
from litestar.di import NamedDependency
from sqlalchemy import Subquery, and_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.expression import select

from SimplyTransport.domain.agency.model import AgencyModel
from SimplyTransport.domain.calendar.model import CalendarModel
from SimplyTransport.domain.calendar_dates.model import CalendarDateModel
from SimplyTransport.domain.database_statistics.model import DatabaseStatisticModel
from SimplyTransport.domain.database_statistics.statistic_type import StatisticType
from SimplyTransport.domain.route.model import RouteModel
from SimplyTransport.domain.shape.model import ShapeModel
from SimplyTransport.domain.stop.model import StopModel
from SimplyTransport.domain.stop_features.model import StopFeatureModel
from SimplyTransport.domain.stop_times.model import StopTimeModel
from SimplyTransport.domain.trip.model import TripModel


def max_created_subquery(statistic_type: StatisticType | None = None, date: date | None = None) -> Subquery:
    """
    Returns a subquery that selects the maximum created_at value for each key
    in the DatabaseStatisticModel table.

    Args:
        statistic_type (StatisticType | None): The statistic type to filter by. Defaults to None.
        date (date | None): The date to filter by. Defaults to None.

    Returns:
        Subquery: A subquery that selects the maximum created_at value for each key.
    """
    query = select(
        DatabaseStatisticModel.key,
        func.max(DatabaseStatisticModel.created_at).label("max_created_at"),
    ).group_by(DatabaseStatisticModel.key)

    if statistic_type is not None:
        query = query.where(DatabaseStatisticModel.statistic_type == statistic_type)
    if date is not None:
        query = query.where(func.date(DatabaseStatisticModel.created_at) == date)

    return query.alias("subquery")


class DatabaseStatisticRepository(SQLAlchemyAsyncRepository[DatabaseStatisticModel]):  # type: ignore
    """Database Statistic repository."""

    async def get_gtfs_record_counts(self) -> dict[str, int | None]:
        """Returns a dictionary of the counts of each GTFS record type."""

        record_counts = {
            "Operators": (await self.session.execute(select(func.count()).select_from(AgencyModel))).scalar(),
            "Routes": (await self.session.execute(select(func.count()).select_from(RouteModel))).scalar(),
            "Trips": (await self.session.execute(select(func.count()).select_from(TripModel))).scalar(),
            "Stops": (await self.session.execute(select(func.count()).select_from(StopModel))).scalar(),
            "Stop Features": (
                await self.session.execute(select(func.count()).select_from(StopFeatureModel))
            ).scalar(),
            "Calendars": (
                await self.session.execute(select(func.count()).select_from(CalendarModel))
            ).scalar(),
            "Calendar Dates": (
                await self.session.execute(select(func.count()).select_from(CalendarDateModel))
            ).scalar(),
            "Stop Times": (
                await self.session.execute(select(func.count()).select_from(StopTimeModel))
            ).scalar(),
            "Shapes": (await self.session.execute(select(func.count()).select_from(ShapeModel))).scalar(),
        }

        return record_counts

    async def get_operator_route_counts(self) -> dict[str, int | None]:
        """Returns a dictionary of the counts of each operator's routes."""

        route_counts = (
            await self.session.execute(
                select(AgencyModel.name, func.count(RouteModel.id))
                .join(RouteModel, RouteModel.agency_id == AgencyModel.id)
                .group_by(AgencyModel.name)
            )
        ).all()

        return {name: count for name, count in route_counts}  # noqa: C416

    async def get_operator_trip_counts(self) -> dict[str, int | None]:
        """Returns a dictionary of the counts of each operator's trips."""

        trip_counts = (
            await self.session.execute(
                select(AgencyModel.name, func.count(TripModel.id))
                .join(RouteModel, RouteModel.agency_id == AgencyModel.id)
                .join(TripModel, TripModel.route_id == RouteModel.id)
                .group_by(AgencyModel.name)
            )
        ).all()

        return {name: count for name, count in trip_counts}  # noqa: C416

    async def get_stop_feature_counts(self) -> dict[str, int | None]:
        """Returns a dictionary of the counts of each stop feature type."""

        record_counts = {
            "Surveyed Stops": (
                await self.session.execute(
                    select(func.count())
                    .select_from(StopFeatureModel)
                    .where(StopFeatureModel.surveyed == True)  # noqa: E712
                )
            ).scalar(),
            "Unsurveyed Stops": (
                await self.session.execute(
                    select(func.count())
                    .select_from(StopFeatureModel)
                    .where(StopFeatureModel.surveyed == False)  # noqa: E712
                )
            ).scalar(),
            "Stops with no features": (
                await self.session.execute(
                    select(func.count())
                    .select_from(StopModel)
                    .join(StopFeatureModel, StopModel.id == StopFeatureModel.stop_id, isouter=True)
                    .where(StopFeatureModel.id == None)  # noqa: E711
                )
            ).scalar(),
            "Wheelchair Accessible": (
                await self.session.execute(
                    select(func.count())
                    .select_from(StopFeatureModel)
                    .where(StopFeatureModel.wheelchair_accessability == True)  # noqa: E712
                )
            ).scalar(),
            "RealTime Display": (
                await self.session.execute(
                    select(func.count()).select_from(StopFeatureModel).where(StopFeatureModel.rtpi_active)
                )
            ).scalar(),
            "Shelter Available": (
                await self.session.execute(
                    select(func.count()).select_from(StopFeatureModel).where(StopFeatureModel.shelter_active)
                )
            ).scalar(),
            "Light Available(Shelter)": (
                await self.session.execute(
                    select(func.count()).select_from(StopFeatureModel).where(StopFeatureModel.light == True)  # noqa: E712
                )
            ).scalar(),
            "Bench Available": (
                await self.session.execute(
                    select(func.count()).select_from(StopFeatureModel).where(StopFeatureModel.bench == True)  # noqa: E712
                )
            ).scalar(),
            "Bin Available": (
                await self.session.execute(
                    select(func.count()).select_from(StopFeatureModel).where(StopFeatureModel.bin == True)  # noqa: E712
                )
            ).scalar(),
        }

        return record_counts

    async def add_row_counts(self, row_counts: dict[str, int | None], statistic_type: StatisticType) -> None:
        """Adds a row count entry to the database."""

        for key, value in row_counts.items():
            self.session.add(
                DatabaseStatisticModel(
                    statistic_type=statistic_type,
                    key=key,
                    value=value if value is not None else 0,
                )
            )

        await self.session.commit()

    async def get_statistics_most_recent_by_type(self, type: StatisticType) -> list[DatabaseStatisticModel]:
        """Returns the most recent statistics for a given type."""

        subquery = max_created_subquery(type)

        stats = (
            (
                await self.session.execute(
                    select(DatabaseStatisticModel)
                    .join(
                        subquery,
                        and_(
                            DatabaseStatisticModel.key == subquery.c.key,
                            DatabaseStatisticModel.created_at == subquery.c.max_created_at,
                        ),
                    )
                    .order_by(DatabaseStatisticModel.key)
                )
            )
            .scalars()
            .all()
        )

        return list[DatabaseStatisticModel](stats)

    async def get_statistics_by_type_and_date(
        self, type: StatisticType, date: date
    ) -> list[DatabaseStatisticModel]:
        """Returns the statistics for a given type on a given date."""

        subquery = max_created_subquery(type, date)

        stats = (
            (
                await self.session.execute(
                    select(DatabaseStatisticModel)
                    .join(
                        subquery,
                        and_(
                            DatabaseStatisticModel.key == subquery.c.key,
                            DatabaseStatisticModel.created_at == subquery.c.max_created_at,
                        ),
                    )
                    .where(func.date(DatabaseStatisticModel.created_at) == date)
                    .order_by(DatabaseStatisticModel.key)
                )
            )
            .scalars()
            .all()
        )

        return list(stats)

    model_type = DatabaseStatisticModel


async def provide_database_statistic_repo(
    db_session: NamedDependency[AsyncSession],
) -> DatabaseStatisticRepository:
    """This provides the Database Statistic repository."""

    return DatabaseStatisticRepository(session=db_session)
