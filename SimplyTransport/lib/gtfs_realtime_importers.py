import asyncio
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from json import JSONDecodeError
from typing import Any

import httpx
import rich.progress as rp
from SimplyTransport.lib.tracing import CreateSpan
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..domain.realtime.enums import ScheduleRealtionship
from ..domain.realtime.stop_time.model import RTStopTimeModel
from ..domain.realtime.trip.model import RTTripModel
from ..domain.realtime.vehicle.model import RTVehicleModel
from ..domain.route.model import RouteModel
from ..domain.stop.model import StopModel
from ..domain.trip.model import TripModel
from . import time_date_conversions as tdc
from .db.database import async_session_factory
from .logging.logging import provide_logger
from .sqlalchemy_bulk import bulk_insert, bulk_upsert

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

RETENTION_PERIOD = datetime.now(UTC) - timedelta(minutes=30)
HTTP_TIMEOUT_SECONDS = 5.0
HTTP_MAX_RETRIES = 2
HTTP_RETRY_DELAY_SECONDS = 1.0
HTTP_MAX_ATTEMPTS = HTTP_MAX_RETRIES + 1


@dataclass(frozen=True)
class RealtimeImportSharedContext:
    """Trip ids present in static GTFS for a dataset; shared by parallel RT importers."""

    trips_in_db: frozenset[str]


async def _shared_context_from_session(session: AsyncSession, dataset: str) -> RealtimeImportSharedContext:
    result = await session.execute(select(TripModel.id).where(TripModel.dataset == dataset))
    return RealtimeImportSharedContext(frozenset[str](result.scalars()))


async def load_realtime_import_shared_context(dataset: str) -> RealtimeImportSharedContext:
    """Load static trip ids for ``dataset`` (opens one session)."""
    async with async_session_factory() as session:
        return await _shared_context_from_session(session, dataset)


def _trip_descriptor_relationship(trip: dict[str, Any]) -> str:
    rel = trip.get("schedule_relationship")
    return rel if rel else ScheduleRealtionship.SCHEDULED.value


def _effective_trip_id_for_trip_update(trip_update: dict[str, Any]) -> str | None:
    """DB trip id: ``trip_properties.trip_id`` for DUPLICATED when set, else descriptor ``trip_id``."""
    trip = trip_update.get("trip") or {}
    props = trip_update.get("trip_properties") or {}
    rel = _trip_descriptor_relationship(trip)
    if rel == ScheduleRealtionship.DUPLICATED.value and props.get("trip_id"):
        return str(props["trip_id"])
    tid = trip.get("trip_id")
    return str(tid) if tid else None


def _skip_stop_time_import_for_trip_relationship(rel: str) -> bool:
    return rel in (ScheduleRealtionship.CANCELED.value, ScheduleRealtionship.DELETED.value)


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

    async def clear_table_stop_trip(self):
        """Clears the table in the database that corresponds to the dataset for rows older than 60 mins"""

        async with async_session_factory() as session:
            delete_stoptime = delete(RTStopTimeModel).where(
                RTStopTimeModel.created_at < RETENTION_PERIOD,
                RTStopTimeModel.dataset == self.dataset,
            )
            await session.execute(delete_stoptime)

            delete_trip = delete(RTTripModel).where(
                RTTripModel.created_at < RETENTION_PERIOD,
                RTTripModel.dataset == self.dataset,
            )
            await session.execute(delete_trip)

            await session.commit()

    async def import_from_payload(self, data: dict) -> tuple[int, int]:
        """Import trip updates and stop times from an in-memory GTFS-RT payload (used by CLI seed)."""
        await self.clear_table_stop_trip()
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

        async with async_session_factory() as session:
            objects_to_commit: list[dict] = []

            result_stops = await session.execute(
                select(StopModel.id).where(StopModel.dataset == self.dataset)
            )
            stops_in_db = frozenset[str](result_stops.scalars())

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

                        st_rel = stop_time.get("schedule_relationship") or (
                            ScheduleRealtionship.SCHEDULED.value
                        )
                        arrival = stop_time.get("arrival") or {}
                        departure = stop_time.get("departure") or {}

                        new_rt_stop_time = {
                            "stop_id": sid,
                            "trip_id": eff_trip_id,
                            "stop_sequence": stop_seq,
                            "schedule_relationship": st_rel,
                            "arrival_delay": arrival.get("delay"),
                            "departure_delay": departure.get("delay"),
                            "entity_id": item.get("id"),
                            "dataset": self.dataset,
                        }

                        objects_to_commit.append(new_rt_stop_time)
                        progress.update(task, advance=1)

                if objects_to_commit:
                    try:
                        await bulk_upsert(
                            session,
                            RTStopTimeModel,
                            objects_to_commit,
                            ["stop_id", "trip_id", "stop_sequence", "dataset"],
                            {
                                "arrival_delay": "arrival_delay",
                                "departure_delay": "departure_delay",
                                "schedule_relationship": "schedule_relationship",
                                "entity_id": "entity_id",
                                "dataset": "dataset",
                            },
                        )
                    except Exception as e:
                        logger.error(f"RealTime: {self.url} failed to commit stop times: {e}")
                        return 0
                return len(objects_to_commit)
            except Exception as e:
                logger.warning(f"RealTime: {self.url} returned invalid JSON in entities: {e}")
                return 0

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

        async with async_session_factory() as session:
            objects_to_commit: list[dict] = []
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

                new_rt_trip = {
                    "trip_id": eff_trip_id,
                    "route_id": route_id,
                    "start_time": start_time,
                    "start_date": start_date,
                    "schedule_relationship": rel,
                    "direction": direction,
                    "entity_id": str(item.get("id") or ""),
                    "dataset": self.dataset,
                }

                objects_to_commit.append(new_rt_trip)
                progress.update(task, advance=1)

            if objects_to_commit:
                try:
                    await bulk_upsert(
                        session,
                        RTTripModel,
                        objects_to_commit,
                        ["trip_id", "route_id", "dataset"],
                        {
                            "start_time": "start_time",
                            "start_date": "start_date",
                            "schedule_relationship": "schedule_relationship",
                            "direction": "direction",
                            "entity_id": "entity_id",
                            "dataset": "dataset",
                        },
                    )
                except Exception as e:
                    logger.error(f"RealTime: {self.url} failed to commit trips: {e}")
                    return 0
            return len(objects_to_commit)


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

    async def clear_table_vehicles(self):
        """Clears the table in the database that corresponds to the dataset for rows older than 60 mins"""

        async with async_session_factory() as session:
            delete_vehicles = delete(RTVehicleModel).where(
                RTVehicleModel.created_at < RETENTION_PERIOD,
                RTVehicleModel.dataset == self.dataset,
            )
            await session.execute(delete_vehicles)
            await session.commit()

    @CreateSpan()
    async def import_vehicles(self, data: dict) -> int:
        """Imports the vehicles from the dataset into the database"""

        entities = data.get("entity", [])
        objects_to_commit: list[dict] = []
        with rp.Progress(*progress_columns) as progress:
            task = progress.add_task("[green]Importing RT Vehicles...", total=max(len(entities), 1))

            async with async_session_factory() as session:
                shared = await _shared_context_from_session(session, self.dataset)

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

                        objects_to_commit.append(
                            {
                                "vehicle_id": int(vid),
                                "trip_id": trip_id,
                                "time_of_update": datetime.fromtimestamp(int(ts)),
                                "lat": lat,
                                "lon": lon,
                                "dataset": self.dataset,
                            }
                        )
                        progress.update(task, advance=1)

                    if objects_to_commit:
                        try:
                            await bulk_insert(session, RTVehicleModel, objects_to_commit)
                        except Exception as e:
                            logger.error(f"RealTime: {self.url} failed to commit vehicles: {e}")
                            return 0
                except Exception as e:
                    logger.warning(f"RealTime: {self.url} returned invalid JSON in entities: {e}")
                    return 0

        return len(objects_to_commit)
