import asyncio
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from json import JSONDecodeError
from typing import Any

import httpx
import rich.progress as rp
from SimplyTransport.lib.tracing import CreateSpan
from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from ..domain.realtime.enums import ScheduleRelationship
from ..domain.realtime.stop_time.rt_stop_time_model import RTStopTimeModel
from ..domain.realtime.trip.rt_trip_model import RTTripModel
from ..domain.realtime.vehicle.rt_vehicle_model import RTVehicleModel
from ..domain.route.route_model import RouteModel
from ..domain.stop.stop_model import StopModel
from ..domain.trip.trip_model import TripModel
from . import time_date_conversions as tdc
from .db.database import async_session_factory, get_async_engine
from .gtfs_importers import (
    ClearStrategy,
    choose_clear_strategy,
    records_with_ids,
    reserve_id_range,
)
from .logging.logging import provide_logger

logger = provide_logger(__name__)

progress_columns = (
    rp.SpinnerColumn(finished_text="✅"),
    "[progress.description]{task.description}",
    rp.BarColumn(),
    rp.MofNCompleteColumn(),
    rp.TaskProgressColumn(),
    "|| Taken:",
    rp.TimeElapsedColumn(),
    "|| Left:",
    rp.TimeRemainingColumn(),
)

HTTP_TIMEOUT_SECONDS = 5.0
HTTP_MAX_RETRIES = 2
HTTP_RETRY_DELAY_SECONDS = 1.0
HTTP_MAX_ATTEMPTS = HTTP_MAX_RETRIES + 1

RT_TRIP_COPY_COLUMNS = (
    "trip_id",
    "route_id",
    "start_time",
    "start_date",
    "schedule_relationship",
    "direction",
    "entity_id",
    "dataset",
    "created_at",
)
RT_STOP_TIME_COPY_COLUMNS = (
    "stop_id",
    "trip_id",
    "stop_sequence",
    "schedule_relationship",
    "arrival_delay",
    "departure_delay",
    "entity_id",
    "dataset",
    "created_at",
)
RT_VEHICLE_COPY_COLUMNS = (
    "vehicle_id",
    "trip_id",
    "time_of_update",
    "lat",
    "lon",
    "dataset",
    "created_at",
)
RT_TRIP_DEDUP_INDEXES = (0, 1, 7)
RT_STOP_TIME_DEDUP_INDEXES = (0, 1, 2, 7)
RT_VEHICLE_DEDUP_INDEXES = (0, 5)
RT_TRIP_ID_SEQUENCE = "rt_trip_id_seq"
RT_STOP_TIME_ID_SEQUENCE = "rt_stop_time_id_seq"
RT_VEHICLE_ID_SEQUENCE = "rt_vehicle_id_seq"


@dataclass(frozen=True)
class RealtimeImportSharedContext:
    """Trip ids present in static GTFS for a dataset; shared by parallel RT importers."""

    trips_in_db: frozenset[str]


def rt_trip_record(
    trip_id: str,
    route_id: str,
    start_time: time,
    start_date: date,
    schedule_relationship: str,
    direction: int,
    entity_id: str,
    dataset: str,
    created_at: datetime,
) -> tuple:
    return (
        trip_id,
        route_id,
        start_time,
        start_date,
        schedule_relationship,
        direction,
        entity_id,
        dataset,
        created_at,
    )


def rt_stop_time_record(
    stop_id: str,
    trip_id: str,
    stop_sequence: int,
    schedule_relationship: str,
    arrival_delay: int | None,
    departure_delay: int | None,
    entity_id: str,
    dataset: str,
    created_at: datetime,
) -> tuple:
    return (
        stop_id,
        trip_id,
        stop_sequence,
        schedule_relationship,
        arrival_delay,
        departure_delay,
        entity_id,
        dataset,
        created_at,
    )


def rt_vehicle_record(
    vehicle_id: int,
    trip_id: str,
    time_of_update: datetime,
    lat: float,
    lon: float,
    dataset: str,
    created_at: datetime,
) -> tuple:
    return (vehicle_id, trip_id, time_of_update, lat, lon, dataset, created_at)


def dedup_records_by_key(records: list[tuple], key_indexes: Sequence[int]) -> list[tuple]:
    """Keep the last row for each key (later feed entities win)."""
    latest: dict[tuple, tuple] = {}
    for record in records:
        latest[tuple(record[i] for i in key_indexes)] = record
    return list(latest.values())


async def snapshot_copy_table(
    *,
    model: type,
    table_name: str,
    columns: tuple[str, ...],
    records: list[tuple],
    dataset: str,
    id_sequence: str,
) -> None:
    """Replace ``dataset`` rows in ``table_name`` with ``records`` in one transaction."""
    engine = get_async_engine()
    async with engine.begin() as conn:
        other = await conn.execute(select(model.dataset).where(model.dataset != dataset).limit(1))
        strategy = choose_clear_strategy(
            other_dataset_exists=other.scalar_one_or_none() is not None,
            table_name=table_name,
        )
        if strategy is ClearStrategy.DELETE:
            await conn.execute(delete(model).where(model.dataset == dataset))
        elif strategy is ClearStrategy.TRUNCATE_CASCADE:
            await conn.execute(text(f'TRUNCATE TABLE "{table_name}" RESTART IDENTITY CASCADE'))
        else:
            await conn.execute(text(f'TRUNCATE TABLE "{table_name}" RESTART IDENTITY'))

        if not records:
            return

        raw = await conn.get_raw_connection()
        asyncpg_conn = raw.driver_connection
        if asyncpg_conn is None:
            msg = "Could not get asyncpg connection for COPY"
            raise RuntimeError(msg)

        first_id = await reserve_id_range(asyncpg_conn, id_sequence, len(records))
        await asyncpg_conn.copy_records_to_table(
            table_name,
            records=records_with_ids(records, first_id),
            columns=("id", *columns),
        )


async def _shared_context_from_session(session: AsyncSession, dataset: str) -> RealtimeImportSharedContext:
    result = await session.execute(select(TripModel.id).where(TripModel.dataset == dataset))
    return RealtimeImportSharedContext(frozenset[str](result.scalars()))


async def load_realtime_import_shared_context(dataset: str) -> RealtimeImportSharedContext:
    """Load static trip ids for ``dataset`` (opens one session)."""
    async with async_session_factory() as session:
        return await _shared_context_from_session(session, dataset)


def _trip_descriptor_relationship(trip: dict[str, Any]) -> str:
    rel = trip.get("schedule_relationship")
    return rel if rel else ScheduleRelationship.SCHEDULED.value


def _effective_trip_id_for_trip_update(trip_update: dict[str, Any]) -> str | None:
    """DB trip id: ``trip_properties.trip_id`` for DUPLICATED when set, else descriptor ``trip_id``."""
    trip = trip_update.get("trip") or {}
    props = trip_update.get("trip_properties") or {}
    rel = _trip_descriptor_relationship(trip)
    if rel == ScheduleRelationship.DUPLICATED.value and props.get("trip_id"):
        return str(props["trip_id"])
    tid = trip.get("trip_id")
    return str(tid) if tid else None


def _skip_stop_time_import_for_trip_relationship(rel: str) -> bool:
    return rel in (ScheduleRelationship.CANCELED.value, ScheduleRelationship.DELETED.value)


def _parse_rt_start_time(time_str: str | None) -> time:
    if not time_str:
        return time(0, 0, 0)
    return tdc.convert_29_hours_to_24_hours(time_str)


def _parse_rt_start_date(date_str: str | None, fallback: date) -> date:
    if not date_str:
        return fallback
    return tdc.convert_joined_date_to_date(date_str)


async def _fetch_realtime_json(url: str, api_key: str) -> dict | None:
    headers = {
        "Cache-Control": "no-cache",
        "x-api-key": api_key,
    }

    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT_SECONDS) as client:
        for attempt in range(1, HTTP_MAX_ATTEMPTS + 1):
            try:
                response = await client.get(url, headers=headers)
            except httpx.RequestError as e:
                logger.warning(
                    f"RealTime: {url} request failed on attempt {attempt}/{HTTP_MAX_ATTEMPTS}: {e}"
                )
            else:
                if 400 <= response.status_code < 500:
                    logger.warning(f"RealTime: {url} returned {response.status_code}")
                    return None
                if response.status_code != 200:
                    logger.warning(
                        f"RealTime: {url} returned {response.status_code} "
                        f"on attempt {attempt}/{HTTP_MAX_ATTEMPTS}"
                    )
                else:
                    try:
                        return response.json()
                    except JSONDecodeError as e:
                        logger.error(
                            f"RealTime: {url} returned invalid JSON "
                            f"on attempt {attempt}/{HTTP_MAX_ATTEMPTS}: {e}"
                        )

            if attempt == HTTP_MAX_ATTEMPTS:
                logger.warning(f"RealTime: {url} failed after {HTTP_MAX_ATTEMPTS} attempts")
                return None
            await asyncio.sleep(HTTP_RETRY_DELAY_SECONDS)

    return None


class RealTimeImporter:
    def __init__(self, url: str, api_key: str, dataset: str) -> None:
        self.url = url
        self.api_key = api_key
        self.dataset = dataset

    async def get_data(self) -> dict | None:
        return await _fetch_realtime_json(self.url, self.api_key)

    async def import_from_payload(self, data: dict) -> tuple[int, int]:
        """Import trip updates and stop times from an in-memory GTFS-RT payload (used by CLI seed)."""
        with rp.Progress(*progress_columns) as progress:
            total_stop_times, total_trips = await asyncio_gather_imports(self, data, progress)
        return total_stop_times, total_trips

    @CreateSpan()
    async def import_stop_times(
        self,
        data: dict,
        progress: rp.Progress,
        shared: RealtimeImportSharedContext,
    ) -> int:
        """Imports the stop times from the dataset into the database"""

        entities = data.get("entity", [])
        stop_time_update_count = sum(
            len((item.get("trip_update") or {}).get("stop_time_update", []))
            for item in entities
            if item.get("trip_update")
            and not _skip_stop_time_import_for_trip_relationship(
                _trip_descriptor_relationship((item.get("trip_update") or {}).get("trip") or {})
            )
        )
        task = progress.add_task("[green]Importing RT Stop Times...", total=max(stop_time_update_count, 1))
        created_at = datetime.now(UTC)

        async with async_session_factory() as session:
            result_stops = await session.execute(
                select(StopModel.id).where(StopModel.dataset == self.dataset)
            )
            stops_in_db = frozenset[str](result_stops.scalars())

        records: list[tuple] = []
        try:
            for item in entities:
                trip_update = item.get("trip_update") or {}
                if not trip_update:
                    continue
                trip = trip_update.get("trip") or {}
                rel = _trip_descriptor_relationship(trip)
                if _skip_stop_time_import_for_trip_relationship(rel):
                    continue

                eff_trip_id = _effective_trip_id_for_trip_update(trip_update)
                if not eff_trip_id or eff_trip_id not in shared.trips_in_db:
                    continue

                for stop_time in trip_update.get("stop_time_update", []):
                    sid = stop_time.get("stop_id")
                    if not sid or sid not in stops_in_db:
                        continue

                    raw_seq = stop_time.get("stop_sequence")
                    if raw_seq is None:
                        continue
                    try:
                        stop_seq = int(raw_seq)
                    except TypeError, ValueError:
                        continue

                    st_rel = stop_time.get("schedule_relationship") or (ScheduleRelationship.SCHEDULED.value)
                    arrival = stop_time.get("arrival") or {}
                    departure = stop_time.get("departure") or {}

                    records.append(
                        rt_stop_time_record(
                            sid,
                            eff_trip_id,
                            stop_seq,
                            st_rel,
                            arrival.get("delay"),
                            departure.get("delay"),
                            str(item.get("id") or ""),
                            self.dataset,
                            created_at,
                        )
                    )
                    progress.update(task, advance=1)
        except Exception as e:
            logger.warning(f"RealTime: {self.url} returned invalid JSON in entities: {e}")
            return 0

        records = dedup_records_by_key(records, RT_STOP_TIME_DEDUP_INDEXES)
        try:
            await snapshot_copy_table(
                model=RTStopTimeModel,
                table_name="rt_stop_time",
                columns=RT_STOP_TIME_COPY_COLUMNS,
                records=records,
                dataset=self.dataset,
                id_sequence=RT_STOP_TIME_ID_SEQUENCE,
            )
        except Exception as e:
            logger.error(f"RealTime: {self.url} failed to commit stop times: {e}")
            return 0
        return len(records)

    @CreateSpan()
    async def import_trips(
        self,
        data: dict,
        progress: rp.Progress,
        shared: RealtimeImportSharedContext,
    ) -> int:
        """Imports the trips from the dataset into the database"""

        entities = [e for e in data.get("entity", []) if e.get("trip_update")]
        trip_update_count = len(entities)
        task = progress.add_task("[green]Importing RT Trips...", total=max(trip_update_count, 1))
        created_at = datetime.now(UTC)

        async with async_session_factory() as session:
            result_routes = await session.execute(
                select(RouteModel.id).where(RouteModel.dataset == self.dataset)
            )
            routes_in_db = frozenset[str](result_routes.scalars())

            trip_meta_rows = await session.execute(
                select(TripModel.id, TripModel.route_id, TripModel.direction).where(
                    TripModel.dataset == self.dataset
                )
            )
            trip_dir = {r.id: (r.route_id, r.direction) for r in trip_meta_rows.all()}
        today = date.today()
        records: list[tuple] = []

        for item in entities:
            trip_update = item.get("trip_update") or {}
            trip = trip_update.get("trip") or {}
            props = trip_update.get("trip_properties") or {}
            rel = _trip_descriptor_relationship(trip)
            eff_trip_id = _effective_trip_id_for_trip_update(trip_update)
            if not eff_trip_id or eff_trip_id not in shared.trips_in_db:
                progress.update(task, advance=1)
                continue

            route_id = trip.get("route_id") or trip_dir.get(eff_trip_id, (None,))[0]
            if not route_id or route_id not in routes_in_db:
                progress.update(task, advance=1)
                continue

            start_time = _parse_rt_start_time(trip.get("start_time"))
            start_date_src = trip.get("start_date") or props.get("start_date")
            start_date = _parse_rt_start_date(start_date_src, today)

            di = trip.get("direction_id")
            if di is not None:
                direction = int(di)
            else:
                static_dir = trip_dir.get(eff_trip_id, (None, None))[1]
                direction = int(static_dir) if static_dir is not None else 0

            records.append(
                rt_trip_record(
                    eff_trip_id,
                    route_id,
                    start_time,
                    start_date,
                    rel,
                    direction,
                    str(item.get("id") or ""),
                    self.dataset,
                    created_at,
                )
            )
            progress.update(task, advance=1)

        records = dedup_records_by_key(records, RT_TRIP_DEDUP_INDEXES)
        try:
            await snapshot_copy_table(
                model=RTTripModel,
                table_name="rt_trip",
                columns=RT_TRIP_COPY_COLUMNS,
                records=records,
                dataset=self.dataset,
                id_sequence=RT_TRIP_ID_SEQUENCE,
            )
        except Exception as e:
            logger.error(f"RealTime: {self.url} failed to commit trips: {e}")
            return 0
        return len(records)


async def asyncio_gather_imports(
    importer: RealTimeImporter, data: dict, progress: rp.Progress
) -> tuple[int, int]:
    shared = await load_realtime_import_shared_context(importer.dataset)
    total_stop_times, total_trips = await asyncio.gather(
        importer.import_stop_times(data, progress, shared),
        importer.import_trips(data, progress, shared),
    )
    return total_stop_times, total_trips


class RealTimeVehiclesImporter:
    def __init__(self, url: str, api_key: str, dataset: str) -> None:
        self.url = url
        self.api_key = api_key
        self.dataset = dataset

    async def get_data(self) -> dict | None:
        return await _fetch_realtime_json(self.url, self.api_key)

    @CreateSpan()
    async def import_vehicles(self, data: dict) -> int:
        """Imports the vehicles from the dataset into the database"""

        entities = data.get("entity", [])
        records: list[tuple] = []
        created_at = datetime.now(UTC)
        with rp.Progress(*progress_columns) as progress:
            task = progress.add_task("[green]Importing RT Vehicles...", total=max(len(entities), 1))
            shared = await load_realtime_import_shared_context(self.dataset)

            try:
                for item in entities:
                    vehicle_update = item.get("vehicle") or {}
                    trip = vehicle_update.get("trip") or {}
                    trip_id = trip.get("trip_id")
                    if not trip_id or trip_id not in shared.trips_in_db:
                        progress.update(task, advance=1)
                        continue

                    vid = vehicle_update.get("vehicle", {}).get("id")
                    ts = vehicle_update.get("timestamp")
                    if vid is None or ts is None:
                        progress.update(task, advance=1)
                        continue

                    pos = vehicle_update.get("position") or {}
                    lat = pos.get("latitude")
                    lon = pos.get("longitude")
                    if lat is None or lon is None:
                        progress.update(task, advance=1)
                        continue

                    records.append(
                        rt_vehicle_record(
                            int(vid),
                            trip_id,
                            datetime.fromtimestamp(int(ts)),
                            lat,
                            lon,
                            self.dataset,
                            created_at,
                        )
                    )
                    progress.update(task, advance=1)
            except Exception as e:
                logger.warning(f"RealTime: {self.url} returned invalid JSON in entities: {e}")
                return 0

        records = dedup_records_by_key(records, RT_VEHICLE_DEDUP_INDEXES)
        try:
            await snapshot_copy_table(
                model=RTVehicleModel,
                table_name="rt_vehicle",
                columns=RT_VEHICLE_COPY_COLUMNS,
                records=records,
                dataset=self.dataset,
                id_sequence=RT_VEHICLE_ID_SEQUENCE,
            )
        except Exception as e:
            logger.error(f"RealTime: {self.url} failed to commit vehicles: {e}")
            return 0
        return len(records)
