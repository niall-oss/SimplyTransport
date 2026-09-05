from litestar import Controller, get
from litestar.di import NamedDependency, Provide
from litestar.response import Template

from ..domain.database_statistics.database_statistic_repo import (
    DatabaseStatisticRepo,
    provide_database_statistic_repo,
)
from ..domain.database_statistics.statistic_type import StatisticType
from ..domain.services.statistics_service import StatisticsService, provide_statistics_service
from ..domain.stop.stop_repo import StopRepo, provide_stop_repo
from ..lib.cache_keys import CacheKeys, simple_key_builder
from ..lib.logging.logging import provide_logger
from ..timescale.ts_stop_times.ts_stop_time_repo import TSStopTimeRepo, provide_ts_stop_time_repo

__all__ = [
    "StatsController",
]

logger = provide_logger(__name__)


class StatsController(Controller):
    dependencies = {
        "stats_repo": Provide(provide_database_statistic_repo),
        "stats_service": Provide(provide_statistics_service),
        "stop_repo": Provide(provide_stop_repo),
        "ts_stop_time_repo": Provide(provide_ts_stop_time_repo),
    }

    @get(
        "/static/most-recent",
        cache=86400,
        cache_key_builder=simple_key_builder(CacheKeys.Statistics.STATIC_STATS_KEY_TEMPLATE),
        name="stats.static_stats",
    )
    async def static_stats(
        self,
        stats_repo: NamedDependency[DatabaseStatisticRepo],
        stats_service: NamedDependency[StatisticsService],
    ) -> Template:
        stats = await stats_repo.get_statistics_most_recent_by_type(StatisticType.GTFS_RECORD_COUNTS)
        stats_with_percentages = stats_service.convert_stats_to_stats_with_percentage_totals(stats)
        stats_with_percentages = stats_service.sort_stats_by_value(stats_with_percentages)

        return Template(
            template_name="stats/static_data.html",
            context={"stats_with_percentages": stats_with_percentages},
        )

    @get(
        "/operators/most-recent",
        cache=86400,
        cache_key_builder=simple_key_builder(CacheKeys.Statistics.OPERATOR_STATS_KEY_TEMPLATE),
        name="stats.operator_stats",
    )
    async def operator_stats(
        self,
        stats_repo: NamedDependency[DatabaseStatisticRepo],
        stats_service: NamedDependency[StatisticsService],
    ) -> Template:
        routes = await stats_repo.get_statistics_most_recent_by_type(StatisticType.OPERATOR_ROUTE_COUNTS)
        routes_with_percentages = stats_service.convert_stats_to_stats_with_percentage_totals(
            routes, total_row_key="Total Routes"
        )
        routes_with_percentages = stats_service.sort_stats_by_value(routes_with_percentages)

        trips = await stats_repo.get_statistics_most_recent_by_type(StatisticType.OPERATOR_TRIP_COUNTS)
        trips_with_percentages = stats_service.convert_stats_to_stats_with_percentage_totals(
            trips, total_row_key="Total Trips"
        )
        trips_with_percentages = stats_service.sort_stats_by_value(trips_with_percentages)

        return Template(
            template_name="stats/operator_data.html",
            context={
                "routes_with_percentages": routes_with_percentages,
                "trips_with_percentages": trips_with_percentages,
            },
        )

    @get(
        "/stop-features/most-recent",
        cache=86400,
        cache_key_builder=simple_key_builder(CacheKeys.Statistics.STOP_FEATURES_STATS_KEY_TEMPLATE),
        name="stats.stop_features",
    )
    async def stop_features(
        self,
        stats_repo: NamedDependency[DatabaseStatisticRepo],
        stats_service: NamedDependency[StatisticsService],
        stop_repo: NamedDependency[StopRepo],
    ) -> Template:
        stats = await stats_repo.get_statistics_most_recent_by_type(StatisticType.STOP_FEATURE_COUNTS)
        total_stop_count = await stop_repo.count()

        stats_with_percentages = stats_service.convert_stats_to_stats_with_percentage_totals(
            stats, total_row_key="Total Stops", total_override=total_stop_count
        )
        stats_with_percentages = stats_service.sort_stats_by_value(stats_with_percentages)

        return Template(
            template_name="stats/stop_features_data.html",
            context={"stats_with_percentages": stats_with_percentages},
        )

    @get(
        "/delays/most-recent",
        cache=86400,
        cache_key_builder=simple_key_builder(CacheKeys.Statistics.DELAYS_STATS_KEY_TEMPLATE),
        name="stats.delays",
    )
    async def delays(
        self,
        stats_repo: NamedDependency[DatabaseStatisticRepo],
        stats_service: NamedDependency[StatisticsService],
        ts_stop_time_repo: NamedDependency[TSStopTimeRepo],
    ) -> Template:
        stats = await stats_repo.get_statistics_most_recent_by_type(StatisticType.DELAY_RECORD_COUNTS)
        total_delay_count = await ts_stop_time_repo.get_total_delay_record_count()

        stats_with_percentages = stats_service.convert_stats_to_stats_with_percentage_totals(
            stats, total_row_key="Total Delay Records", total_override=total_delay_count
        )
        stats_with_percentages = stats_service.sort_stats_by_value(stats_with_percentages)

        return Template(
            template_name="stats/delays_data.html",
            context={"stats_with_percentages": stats_with_percentages},
        )
