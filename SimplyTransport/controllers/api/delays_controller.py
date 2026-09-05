from litestar import Controller, get
from litestar.di import NamedDependency, Provide
from litestar.exceptions import NotFoundException, ValidationException
from litestar.params import FromPath
from SimplyTransport.api_contracts.delays_contracts import (
    TSStopTime,
    TSStopTimeDelayAggregated,
    TSStopTimeForGraph,
)

from ...lib.cache_keys import CacheKeys, key_builder_from_path
from ...lib.parameters.time_query import EndDateTimeQuery, ScheduledTimePath, StartDateTimeQuery
from ...lib.time_date_conversions import validate_time_range
from ...timescale.ts_stop_times.ts_stop_time_repo import (
    MAXIMUM_LIMIT,
    MAXIMUM_TIMESTAMP,
    TSStopTimeRepo,
    provide_ts_stop_time_repo,
)

__all__ = ["DelaysController"]


class DelaysController(Controller):
    dependencies = {"repo": Provide(provide_ts_stop_time_repo)}

    @get(
        "/{stop_id:str}/{route_code:str}/{scheduled_time:str}/aggregated",
        cache=86400,
        cache_key_builder=key_builder_from_path(
            CacheKeys.Delays.DELAYS_AGGREGATED_SPECIFIC_KEY_TEMPLATE,
            "stop_id",
            "route_code",
            "scheduled_time",
        ),
        summary="Get aggregated delay data for a route on a stop on a time",
        description=f"All queries will be limited to {MAXIMUM_TIMESTAMP.strftime('%Y-%m-%d')} onwards",
        raises=[NotFoundException, ValidationException],
    )
    async def get_aggregated_delay_on_stop_on_route_on_time(
        self,
        stop_id: FromPath[str],
        route_code: FromPath[str],
        repo: NamedDependency[TSStopTimeRepo],
        scheduled_time: ScheduledTimePath,
        start_time: StartDateTimeQuery = None,
        end_time: EndDateTimeQuery = None,
    ) -> TSStopTimeDelayAggregated:
        validate_time_range(start_time, end_time)
        result = await repo.get_aggregated_delay_on_stop_on_route_on_time(
            route_code, stop_id, scheduled_time, start_time, end_time
        )

        if not result:
            raise NotFoundException(detail=f"Delays not found for {stop_id}, {route_code}, {scheduled_time}")
        return result

    @get(
        "/{stop_id:str}/{route_code:str}/{scheduled_time:str}",
        cache=86400,
        cache_key_builder=key_builder_from_path(
            CacheKeys.Delays.DELAYS_SPECIFIC_KEY_TEMPLATE,
            "stop_id",
            "route_code",
            "scheduled_time",
        ),
        summary="Get delay data for a route on a stop on a time",
        description=f"All queries will be limited to {MAXIMUM_TIMESTAMP.strftime('%Y-%m-%d')} "
        f"onwards or {MAXIMUM_LIMIT} records",
        raises=[ValidationException],
    )
    async def get_delay_on_stop_on_route_on_time(
        self,
        stop_id: FromPath[str],
        route_code: FromPath[str],
        repo: NamedDependency[TSStopTimeRepo],
        scheduled_time: ScheduledTimePath,
        start_time: StartDateTimeQuery = None,
        end_time: EndDateTimeQuery = None,
    ) -> list[TSStopTime]:
        if start_time and end_time and start_time > end_time:
            raise ValidationException(
                detail=f"Start time cannot be greater than end time {start_time} > {end_time}"
            )

        result = await repo.get_delay_on_stop_on_route_on_time(
            route_code, stop_id, scheduled_time, start_time, end_time
        )

        return [TSStopTime.model_validate(obj) for obj in result]

    @get(
        "/{stop_id:str}/{route_code:str}/{scheduled_time:str}/truncated",
        cache=86400,
        cache_key_builder=key_builder_from_path(
            CacheKeys.Delays.DELAYS_SPECIFIC_SLIM_KEY_TEMPLATE,
            "stop_id",
            "route_code",
            "scheduled_time",
        ),
        summary="Get truncated delay data for a route on a stop on a time",
        description=f"All queries will be limited to {MAXIMUM_TIMESTAMP.strftime('%Y-%m-%d')} "
        f"onwards or {MAXIMUM_LIMIT} records",
        raises=[ValidationException],
    )
    async def get_truncated_delay_on_stop_on_route_on_time(
        self,
        stop_id: FromPath[str],
        route_code: FromPath[str],
        repo: NamedDependency[TSStopTimeRepo],
        scheduled_time: ScheduledTimePath,
        start_time: StartDateTimeQuery = None,
        end_time: EndDateTimeQuery = None,
    ) -> list[TSStopTimeForGraph]:
        validate_time_range(start_time, end_time)
        result = await repo.get_truncated_delay_on_stop_on_route_on_time(
            route_code, stop_id, scheduled_time, start_time, end_time
        )

        return [TSStopTimeForGraph.model_validate(obj) for obj in result]

    @get(
        "/{route_code:str}/aggregated",
        cache=86400,
        cache_key_builder=key_builder_from_path(
            CacheKeys.Delays.DELAYS_AGGREGATED_ROUTE_KEY_TEMPLATE,
            "route_code",
        ),
        summary="Get aggregated delay data for a route",
        description=f"All queries will be limited to {MAXIMUM_TIMESTAMP.strftime('%Y-%m-%d')} onwards",
        raises=[NotFoundException, ValidationException],
    )
    async def get_aggregated_delay_on_route(
        self,
        route_code: FromPath[str],
        repo: NamedDependency[TSStopTimeRepo],
        start_time: StartDateTimeQuery = None,
        end_time: EndDateTimeQuery = None,
    ) -> TSStopTimeDelayAggregated:
        validate_time_range(start_time, end_time)
        result = await repo.get_aggregated_delay_on_stop_on_route_on_time(
            route_code, start_time=start_time, end_time=end_time
        )

        if not result:
            raise NotFoundException(detail=f"Delays not found for {route_code}")
        return result
