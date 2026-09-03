from litestar.di import NamedDependency
from SimplyTransport.domain.database_statistics.model import (
    DatabaseStatisticModel,
    DatabaseStatisticWithPercentage,
)
from SimplyTransport.domain.database_statistics.statistic_type import StatisticType
from sqlalchemy.ext.asyncio import AsyncSession

from ...timescale.ts_stop_times.repo import TSStopTimeRepository
from ..database_statistics.repo import DatabaseStatisticRepository


class StatisticsService:
    def __init__(
        self,
        database_statistic_repository: DatabaseStatisticRepository,
        ts_stop_time_repository: TSStopTimeRepository,
    ):
        self.database_statistic_repository = database_statistic_repository
        self.ts_stop_time_repository = ts_stop_time_repository

    async def update_all_statistics(self) -> None:
        """Updates all statistics."""

        await self.update_gtfs_row_counts()
        await self.update_operator_row_counts()
        await self.update_stop_feature_counts()
        await self.update_delay_record_counts()

    async def update_gtfs_row_counts(self) -> None:
        """Updates the GTFS row counts."""

        row_counts = await self.database_statistic_repository.get_gtfs_record_counts()
        await self.database_statistic_repository.add_row_counts(row_counts, StatisticType.GTFS_RECORD_COUNTS)

    async def update_operator_row_counts(self) -> None:
        """Updates the operator row counts."""

        route_counts = await self.database_statistic_repository.get_operator_route_counts()
        await self.database_statistic_repository.add_row_counts(
            route_counts, StatisticType.OPERATOR_ROUTE_COUNTS
        )

        trip_counts = await self.database_statistic_repository.get_operator_trip_counts()
        await self.database_statistic_repository.add_row_counts(
            trip_counts, StatisticType.OPERATOR_TRIP_COUNTS
        )

    async def update_stop_feature_counts(self) -> None:
        """Updates the stop feature counts."""

        stop_feature_counts = await self.database_statistic_repository.get_stop_feature_counts()
        await self.database_statistic_repository.add_row_counts(
            stop_feature_counts, StatisticType.STOP_FEATURE_COUNTS
        )

    async def update_delay_record_counts(self) -> None:
        """Updates the delay record counts."""

        daily_delay_record_counts = (
            await self.ts_stop_time_repository.get_delay_record_counts_for_last_n_hours(24)
        )
        await self.database_statistic_repository.add_row_counts(
            daily_delay_record_counts, StatisticType.DELAY_RECORD_COUNTS
        )

        weekly_delay_record_counts = (
            await self.ts_stop_time_repository.get_delay_record_counts_for_last_n_hours(24 * 7)
        )
        await self.database_statistic_repository.add_row_counts(
            weekly_delay_record_counts, StatisticType.DELAY_RECORD_COUNTS
        )

        monthly_delay_record_counts = (
            await self.ts_stop_time_repository.get_delay_record_counts_for_last_n_hours(24 * 30)
        )
        await self.database_statistic_repository.add_row_counts(
            monthly_delay_record_counts, StatisticType.DELAY_RECORD_COUNTS
        )

    def convert_stats_to_stats_with_percentage_totals(
        self,
        stats: list[DatabaseStatisticModel],
        decimals_places_to_round: int = 2,
        add_totals_row: bool = True,
        total_row_key: str = "Total Rows",
        total_override: int | None = None,
    ) -> list[DatabaseStatisticWithPercentage]:
        """
        Converts a list of DatabaseStatisticModel objects to a list of DatabaseStatisticWithPercentage objects
        with the addition of a totals row if specified.

        Args:
            stats (List[DatabaseStatisticModel]): The list of DatabaseStatisticModel objects to convert.
            decimals_places_to_round (int, optional): The number of decimal places to round the
            percentages to.
                Defaults to 2.
            add_totals_row (bool, optional): Whether to add a totals row to the resulting list.
                Defaults to True.
            total_row_key (str, optional): The key for the totals row.
                Defaults to "Total Rows".
            total_override (int | None, optional): An optional override for the total number of rows.
            If provided, this value will be used instead of calculating the sum of the values
            in the stats list.
                Defaults to None.

        Returns:
            List[DatabaseStatisticWithPercentage]: The list of DatabaseStatisticWithPercentage objects,
            including the totals row if specified.
        """
        if total_override is None:
            total_rows = sum(stat.value for stat in stats)
        else:
            total_rows = total_override
        stats_with_percentages: list[DatabaseStatisticWithPercentage] = []

        if add_totals_row:
            stat_for_totals = DatabaseStatisticWithPercentage(
                key=total_row_key,
                value=total_rows,
                percentage=100,
            )
            stats_with_percentages.append(stat_for_totals)

        for stat in stats:
            percentage = round((stat.value / total_rows) * 100, decimals_places_to_round)
            percentage_stat = DatabaseStatisticWithPercentage(
                key=stat.key,
                value=stat.value,
                percentage=percentage,
            )
            stats_with_percentages.append(percentage_stat)
        return stats_with_percentages

    def sort_stats_by_value(
        self, stats: list[DatabaseStatisticWithPercentage], descending: bool = True
    ) -> list[DatabaseStatisticWithPercentage]:
        """
        Sorts a list of DatabaseStatisticWithPercentage objects based on their value.

        Args:
            stats (List[DatabaseStatisticWithPercentage]): The list of statistics to be sorted.
            descending (bool, optional): Specifies whether the sorting should be in descending order.
                Defaults to True.

        Returns:
            List[DatabaseStatisticWithPercentage]: The sorted list of statistics.
        """
        return sorted(stats, key=lambda x: x.value, reverse=descending)


async def provide_statistics_service(
    db_session: NamedDependency[AsyncSession], timescale_db_session: NamedDependency[AsyncSession]
) -> StatisticsService:
    """
    Provides a StatisticsService instance.

    Args:
        db_session (AsyncSession): The database session.
        timescale_db_session (AsyncSession): The timescale database session.
    Returns:
        StatisticsService: A StatisticsService instance.
    """
    return StatisticsService(
        database_statistic_repository=DatabaseStatisticRepository(session=db_session),
        ts_stop_time_repository=TSStopTimeRepository(session=timescale_db_session),
    )
