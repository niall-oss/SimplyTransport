from collections.abc import Sequence
from datetime import datetime, time, timedelta
from typing import Any, cast

from advanced_alchemy.repository import SQLAlchemyAsyncRepository
from litestar.di import NamedDependency
from SimplyTransport.api_contracts.delays_contracts import (
    TSStopTimeDelayAggregated,
    TSStopTimeForGraph,
)
from SimplyTransport.lib.sqlalchemy_bulk import bulk_insert
from sqlalchemy import delete, func, select, text
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from .ts_stop_time_model import TSStopTimeModel

MAXIMUM_LIMIT = 180
MAXIMUM_TIMESTAMP = datetime.now() - timedelta(days=MAXIMUM_LIMIT)


class TSStopTimeRepo(SQLAlchemyAsyncRepository[TSStopTimeModel]):  # type: ignore
    """TSStopTime repository."""

    async def get_aggregated_delay_on_stop_on_route_on_time(
        self,
        route_code: str,
        stop_id: str | None = None,
        scheduled_time: time | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> TSStopTimeDelayAggregated | None:
        """
        Retrieves delay statistics for a specific stop on a specific route at a given scheduled time.
        Args:
            route_code (str): The code of the route.
            stop_id (str): The ID of the stop.
            scheduled_time (time): The scheduled time of the stop.
            start_time (datetime): The start time of the data.
            end_time (datetime): The end time of the data.
        Returns:
            TSStopTimeDelay | None: An instance of TSStopTimeDelay containing delay statistics
            if data is available, otherwise None.
        """

        base_query = """
        SELECT
            AVG(delay_in_seconds) as avg_delay,
            MAX(delay_in_seconds) as max_delay,
            MIN(delay_in_seconds) as min_delay,
            STDDEV(delay_in_seconds) as stddev_delay,
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY delay_in_seconds) as p50_delay,
            PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY delay_in_seconds) as p75_delay,
            PERCENTILE_CONT(0.9) WITHIN GROUP (ORDER BY delay_in_seconds) as p90_delay,
            COUNT(*) as samples
        FROM ts_stop_times
        WHERE route_code = :route_code
          AND "Timestamp" > :max_timestamp
        """

        if start_time:
            base_query += ' AND "Timestamp" >= :start_time'
        if end_time:
            base_query += ' AND "Timestamp" <= :end_time'
        if stop_id:
            base_query += " AND stop_id = :stop_id"
        if scheduled_time:
            base_query += " AND scheduled_time = :scheduled_time"

        statement = text(base_query)

        params = {
            "route_code": route_code,
            "max_timestamp": MAXIMUM_TIMESTAMP,
        }

        if start_time:
            start_time = start_time.replace(tzinfo=None)
            params["start_time"] = start_time
        if end_time:
            end_time = end_time.replace(tzinfo=None)
            params["end_time"] = end_time
        if stop_id:
            params["stop_id"] = stop_id
        if scheduled_time:
            params["scheduled_time"] = scheduled_time

        result = await self.session.execute(statement=statement, params=params)
        row = result.fetchone()

        if row and row.samples > 0:
            return TSStopTimeDelayAggregated(
                avg=int(row.avg_delay),
                max=int(row.max_delay),
                min=int(row.min_delay),
                standard_deviation=round(float(row.stddev_delay), 2) if row.stddev_delay is not None else 0.0,
                p50=int(row.p50_delay),
                p75=int(row.p75_delay),
                p90=int(row.p90_delay),
                samples=row.samples,
            )

        return None

    async def get_delay_on_stop_on_route_on_time(
        self,
        route_code: str,
        stop_id: str,
        scheduled_time: time,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> list[TSStopTimeModel]:
        """
        Retrieve delay information for a specific stop on a route at a scheduled time.
        Args:
            route_code (str): The code of the route.
            stop_id (str): The ID of the stop.
            scheduled_time (time): The scheduled time of the stop.
            start_time (datetime | None, optional): The start time for filtering results. Defaults to None.
            end_time (datetime | None, optional): The end time for filtering results. Defaults to None.
        Returns:
            List[TSStopTimeModel]: A list of TSStopTimeModel instances that match the criteria.
        """

        conditions = []
        if start_time:
            conditions.append(TSStopTimeModel.Timestamp >= start_time)
        if end_time:
            conditions.append(TSStopTimeModel.Timestamp <= end_time)

        statement = (
            select(TSStopTimeModel)
            .where(
                TSStopTimeModel.route_code == route_code,
                TSStopTimeModel.stop_id == stop_id,
                TSStopTimeModel.scheduled_time == scheduled_time,
                TSStopTimeModel.Timestamp > MAXIMUM_TIMESTAMP,
            )
            .order_by(TSStopTimeModel.Timestamp.desc())
            .limit(MAXIMUM_LIMIT)
        )

        if conditions:
            statement = statement.where(*conditions)

        result = await self.session.execute(statement)
        rows = result.scalars().all()

        return list(rows)

    async def get_truncated_delay_on_stop_on_route_on_time(
        self,
        route_code: str,
        stop_id: str,
        scheduled_time: time,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> list[TSStopTimeForGraph]:
        """
        Retrieves a list of truncated delays for a specific stop on a route at a scheduled time.
        Args:
            route_code (str): The code of the route.
            stop_id (str): The ID of the stop.
            scheduled_time (time): The scheduled time of the stop.
            start_time (datetime | None, optional): The start time for filtering the results.
            Defaults to None.
            end_time (datetime | None, optional): The end time for filtering the results.
            Defaults to None.
        Returns:
            List[TSStopTimeForGraph]: A list of TSStopTimeForGraph objects containing the timestamp
            and delay in seconds.
        """

        conditions = []
        if start_time:
            conditions.append(TSStopTimeModel.Timestamp >= start_time)
        if end_time:
            conditions.append(TSStopTimeModel.Timestamp <= end_time)

        statement = (
            select(TSStopTimeModel.Timestamp, TSStopTimeModel.delay_in_seconds)
            .where(
                TSStopTimeModel.route_code == route_code,
                TSStopTimeModel.stop_id == stop_id,
                TSStopTimeModel.scheduled_time == scheduled_time,
                TSStopTimeModel.Timestamp > MAXIMUM_TIMESTAMP,
            )
            .order_by(TSStopTimeModel.Timestamp.desc())
            .limit(MAXIMUM_LIMIT)
        )

        if conditions:
            statement = statement.where(*conditions)

        result = await self.session.execute(statement)
        rows = result.all()

        return [TSStopTimeForGraph(timestamp=row[0], delay_in_seconds=row[1]) for row in rows]

    async def delete_old_delays(self, cutoff_time: datetime) -> int:
        """
        Deletes old delays from the database in batches.
        Args:
            cutoff_time (datetime): The cutoff time for deleting delays.
        Returns:
            int: The number of delays deleted.
        """

        # Delete in batches of 10000
        batch_size = 10000
        total_deleted = 0

        while True:
            statement = delete(TSStopTimeModel).where(TSStopTimeModel.Timestamp < cutoff_time)
            result = cast(
                CursorResult[Any],
                await self.session.execute(statement),
            )
            await self.session.commit()
            total_deleted += result.rowcount
            if result.rowcount < batch_size:
                break
        return total_deleted

    async def get_delay_record_counts_for_last_n_hours(self, hours: int) -> dict[str, int | None]:
        """Returns the number of delay records for the last N hours."""

        cutoff_time = datetime.now() - timedelta(hours=hours)
        if hours < 25:
            key = f"Last {hours} Hours"
        else:
            key = f"Last {hours // 24} Days"

        statement = select(func.count()).where(TSStopTimeModel.Timestamp > cutoff_time)
        result = await self.session.execute(statement)
        return {key: result.scalar()}

    async def get_total_delay_record_count(self) -> int:
        """Returns the total number of delay records."""
        statement = select(func.count()).select_from(TSStopTimeModel)
        result = await self.session.execute(statement)
        return result.scalar() or 0

    async def bulk_insert_delay_records(
        self,
        rows: Sequence[TSStopTimeModel],
        *,
        auto_commit: bool = True,
    ) -> None:
        if not rows:
            return
        # Core INSERT does not apply ORM column defaults; Timestamp is often unset until flush.
        recorded_at = datetime.now()
        dict_rows = [
            {
                "Timestamp": row.Timestamp if row.Timestamp is not None else recorded_at,
                "stop_id": row.stop_id,
                "route_code": row.route_code,
                "scheduled_time": row.scheduled_time,
                "delay_in_seconds": row.delay_in_seconds,
            }
            for row in rows
        ]
        await bulk_insert(
            self.session,
            TSStopTimeModel,
            dict_rows,
            auto_commit=auto_commit,
        )

    model_type = TSStopTimeModel


async def provide_ts_stop_time_repo(
    timescale_db_session: NamedDependency[AsyncSession],
) -> TSStopTimeRepo:
    """This provides the TSStopTime repository."""

    return TSStopTimeRepo(session=timescale_db_session)
