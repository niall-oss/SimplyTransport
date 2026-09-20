import asyncio
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from json import JSONDecodeError
from typing import Any

import httpx
import rich.progress as rp
from SimplyTransport.lib.tracing import CreateSpan, get_app_tracer
from sqlalchemy import delete, select

from ..domain.realtime.enums import ScheduleRelationship
from ..domain.realtime.stop_time.rt_stop_time_model import RTStopTimeModel
from ..domain.realtime.trip.rt_trip_model import RTTripModel
from ..domain.realtime.vehicle.rt_vehicle_model import RTVehicleModel
from ..domain.stop.stop_model import StopModel
from ..domain.trip.trip_model import TripModel
from . import time_date_conversions as tdc
from .db.database import async_session_factory, get_async_engine
from .gtfs_importers import records_with_ids, reserve_id_range
from .logging.logging import provide_logger
from .progress import ProgressTicker

logger = provide_logger(__name__)

progress_columns = (
    rp.SpinnerColumn(finished_text="OK"),
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
    """Static GTFS trip metadata for feed trip ids. Membership is ``trip_id in trip_dir``."""

    trip_dir: dict[str, tuple[str, int]]


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


def _realtime_progress() -> rp.Progress:
    return rp.Progress(*progress_columns, disable=not sys.stdout.isatty())


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
    tracer = get_app_tracer()
    engine = get_async_engine()
    async with engine.begin() as conn:
        with tracer.start_as_current_span(f"realtime.delete.{table_name}"):
            await conn.execute(delete(model).where(model.dataset == dataset))
        if not records:
            return

        raw = await conn.get_raw_connection()
        asyncpg_conn = raw.driver_connection
        if asyncpg_conn is None:
            msg = "Could not get asyncpg connection for COPY"
            raise RuntimeError(msg)

        with tracer.start_as_current_span(f"realtime.copy.{table_name}"):
            first_id = await reserve_id_range(asyncpg_conn, id_sequence, len(records))
            await asyncpg_conn.copy_records_to_table(
                table_name,
                records=records_with_ids(records, first_id),
                columns=("id", *columns),
            )


async def load_realtime_lookups(
    dataset: str, trip_ids: set[str], stop_ids: set[str]
) -> tuple[RealtimeImportSharedContext, frozenset[str]]:
    """Load static trip metadata and stop ids referenced by the feed."""
    trip_dir: dict[str, tuple[str, int]] = {}
    stops_in_db: frozenset[str] = frozenset()
    if not trip_ids and not stop_ids:
        return RealtimeImportSharedContext(trip_dir=trip_dir), stops_in_db

    async with async_session_factory() as session:
        if trip_ids:
            trip_result = await session.execute(
                select(TripModel.id, TripModel.route_id, TripModel.direction).where(
                    TripModel.dataset == dataset,
                    TripModel.id.in_(trip_ids),
                )
            )
            trip_dir = {row.id: (row.route_id, row.direction) for row in trip_result.all()}
        if stop_ids:
            stop_result = await session.execute(
                select(StopModel.id).where(StopModel.dataset == dataset, StopModel.id.in_(stop_ids))
            )
            stops_in_db = frozenset[str](stop_result.scalars())
    return RealtimeImportSharedContext(trip_dir=trip_dir), stops_in_db


async def load_realtime_import_shared_context(
    dataset: str, trip_ids: set[str]
) -> RealtimeImportSharedContext:
    """Load static trip route/direction for feed trip ids in ``dataset``."""
    shared, _stops = await load_realtime_lookups(dataset, trip_ids, set())
    return shared


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


def collect_trip_update_feed_ids(data: dict) -> tuple[set[str], set[str]]:
    """Trip ids (including cancelled) and stop ids from trip-update entities."""
    trip_ids: set[str] = set()
    stop_ids: set[str] = set()
    for item in data.get("entity", []):
        trip_update = item.get("trip_update") or {}
        if not trip_update:
            continue
        trip = trip_update.get("trip") or {}
        rel = _trip_descriptor_relationship(trip)
        tid = _effective_trip_id_for_trip_update(trip_update)
        if tid:
            trip_ids.add(tid)
        if _skip_stop_time_import_for_trip_relationship(rel):
            continue
        for stop_time in trip_update.get("stop_time_update", []):
            sid = stop_time.get("stop_id")
            if sid:
                stop_ids.add(str(sid))
    return trip_ids, stop_ids


def collect_vehicle_trip_ids(data: dict) -> set[str]:
    trip_ids: set[str] = set()
    for item in data.get("entity", []):
        trip_id = ((item.get("vehicle") or {}).get("trip") or {}).get("trip_id")
        if trip_id:
            trip_ids.add(str(trip_id))
    return trip_ids


def build_rt_trip_and_stop_time_records(
    data: dict,
    dataset: str,
    trip_dir: dict[str, tuple[str, int]],
    stops_in_db: frozenset[str],
    *,
    created_at: datetime | None = None,
    progress: rp.Progress | None = None,
    task_id: int | None = None,
) -> tuple[list[tuple], list[tuple]]:
    created_at = created_at or datetime.now(UTC)
    today = datetime.now(UTC).date()
    trip_records: list[tuple] = []
    stop_records: list[tuple] = []

    with ProgressTicker(progress, task_id) as ticker:
        for item in data.get("entity", []):
            ticker.tick()
            trip_update = item.get("trip_update") or {}
            if not trip_update:
                continue
            trip = trip_update.get("trip") or {}
            props = trip_update.get("trip_properties") or {}
            rel = _trip_descriptor_relationship(trip)
            eff_trip_id = _effective_trip_id_for_trip_update(trip_update)
            if not eff_trip_id or eff_trip_id not in trip_dir:
                continue

            static_route_id, static_direction = trip_dir[eff_trip_id]
            route_id = trip.get("route_id") or static_route_id
            if not route_id:
                continue

            di = trip.get("direction_id")
            if di is not None:
                direction = int(di)
            else:
                direction = int(static_direction) if static_direction is not None else 0

            start_time = _parse_rt_start_time(trip.get("start_time"))
            start_date_src = trip.get("start_date") or props.get("start_date")
            start_date = _parse_rt_start_date(start_date_src, today)
            entity_id = str(item.get("id") or "")

            trip_records.append(
                rt_trip_record(
                    eff_trip_id,
                    route_id,
                    start_time,
                    start_date,
                    rel,
                    direction,
                    entity_id,
                    dataset,
                    created_at,
                )
            )

            if _skip_stop_time_import_for_trip_relationship(rel):
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

                st_rel = stop_time.get("schedule_relationship") or ScheduleRelationship.SCHEDULED.value
                arrival = stop_time.get("arrival") or {}
                departure = stop_time.get("departure") or {}
                stop_records.append(
                    rt_stop_time_record(
                        sid,
                        eff_trip_id,
                        stop_seq,
                        st_rel,
                        arrival.get("delay"),
                        departure.get("delay"),
                        entity_id,
                        dataset,
                        created_at,
                    )
                )

    return (
        dedup_records_by_key(trip_records, RT_TRIP_DEDUP_INDEXES),
        dedup_records_by_key(stop_records, RT_STOP_TIME_DEDUP_INDEXES),
    )


def build_rt_vehicle_records(
    data: dict,
    dataset: str,
    trip_dir: dict[str, tuple[str, int]],
    *,
    created_at: datetime | None = None,
    progress: rp.Progress | None = None,
    task_id: int | None = None,
) -> list[tuple]:
    created_at = created_at or datetime.now(UTC)
    records: list[tuple] = []

    with ProgressTicker(progress, task_id) as ticker:
        for item in data.get("entity", []):
            ticker.tick()
            vehicle_update = item.get("vehicle") or {}
            trip = vehicle_update.get("trip") or {}
            trip_id = trip.get("trip_id")
            if not trip_id or trip_id not in trip_dir:
                continue

            vid = vehicle_update.get("vehicle", {}).get("id")
            ts = vehicle_update.get("timestamp")
            if vid is None or ts is None:
                continue

            pos = vehicle_update.get("position") or {}
            lat = pos.get("latitude")
            lon = pos.get("longitude")
            if lat is None or lon is None:
                continue

            records.append(
                rt_vehicle_record(
                    int(vid),
                    trip_id,
                    datetime.fromtimestamp(int(ts), tz=UTC).replace(tzinfo=None),
                    lat,
                    lon,
                    dataset,
                    created_at,
                )
            )

    return dedup_records_by_key(records, RT_VEHICLE_DEDUP_INDEXES)


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
        """Import trip updates and stop times from an in-memory GTFS-RT payload."""
        with _realtime_progress() as progress:
            return await self.import_trip_updates(data, progress)

    @CreateSpan()
    async def import_trip_updates(self, data: dict, progress: rp.Progress) -> tuple[int, int]:
        """Parse trip-update entities once, then snapshot-replace rt_trip and rt_stop_time."""
        tracer = get_app_tracer()
        entities = data.get("entity", [])
        task = progress.add_task("[green]Importing RT trip updates...", total=max(len(entities), 1))

        with tracer.start_as_current_span("RealTimeImporter.parse"):
            trip_ids, stop_ids = collect_trip_update_feed_ids(data)

        shared, stops_in_db = await load_realtime_lookups(self.dataset, trip_ids, stop_ids)

        with tracer.start_as_current_span("RealTimeImporter.build_records"):
            trip_records, stop_records = build_rt_trip_and_stop_time_records(
                data,
                self.dataset,
                shared.trip_dir,
                stops_in_db,
                progress=progress,
                task_id=task,
            )

        try:
            await snapshot_copy_table(
                model=RTTripModel,
                table_name="rt_trip",
                columns=RT_TRIP_COPY_COLUMNS,
                records=trip_records,
                dataset=self.dataset,
                id_sequence=RT_TRIP_ID_SEQUENCE,
            )
            await snapshot_copy_table(
                model=RTStopTimeModel,
                table_name="rt_stop_time",
                columns=RT_STOP_TIME_COPY_COLUMNS,
                records=stop_records,
                dataset=self.dataset,
                id_sequence=RT_STOP_TIME_ID_SEQUENCE,
            )
        except Exception:
            logger.exception(f"RealTime: {self.url} failed to commit trip updates")
            raise
        return len(stop_records), len(trip_records)


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
        tracer = get_app_tracer()
        entities = data.get("entity", [])
        with _realtime_progress() as progress:
            task = progress.add_task("[green]Importing RT Vehicles...", total=max(len(entities), 1))
            with tracer.start_as_current_span("RealTimeVehiclesImporter.parse"):
                trip_ids = collect_vehicle_trip_ids(data)
            shared = await load_realtime_import_shared_context(self.dataset, trip_ids)
            with tracer.start_as_current_span("RealTimeVehiclesImporter.build_records"):
                records = build_rt_vehicle_records(
                    data,
                    self.dataset,
                    shared.trip_dir,
                    progress=progress,
                    task_id=task,
                )

        try:
            await snapshot_copy_table(
                model=RTVehicleModel,
                table_name="rt_vehicle",
                columns=RT_VEHICLE_COPY_COLUMNS,
                records=records,
                dataset=self.dataset,
                id_sequence=RT_VEHICLE_ID_SEQUENCE,
            )
        except Exception:
            logger.exception(f"RealTime: {self.url} failed to commit vehicles")
            raise
        return len(records)
