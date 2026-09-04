import asyncio
import csv
from abc import ABC, abstractmethod
from collections.abc import Iterator, Sequence
from enum import Enum
from typing import Any, ClassVar

import rich.progress as rp
from sqlalchemy import delete, select, text

from ..domain.agency.model import AgencyModel
from ..domain.calendar.model import CalendarModel
from ..domain.calendar_dates.model import CalendarDateModel
from ..domain.enums import RouteType
from ..domain.route.model import RouteModel
from ..domain.shape.model import ShapeModel
from ..domain.stop.model import StopModel
from ..domain.stop_times.model import StopTimeModel
from ..domain.trip.model import TripModel
from . import time_date_conversions as tdc
from .db.database import async_session_factory, get_async_engine
from .db.services import create_secondary_indexes, drop_secondary_indexes

NUMBER_OF_CONSUMERS = 2
QUEUE_MAXSIZE = 2
COPY_BATCH_SIZE = 50_000
TRUNCATE_CASCADE_TABLES = frozenset({"trip", "route", "stop"})

TRIP_CSV_FIELDS = (
    "trip_id",
    "route_id",
    "service_id",
    "shape_id",
    "trip_headsign",
    "trip_short_name",
    "direction_id",
    "block_id",
)
TRIP_COPY_COLUMNS = (
    "id",
    "route_id",
    "service_id",
    "shape_id",
    "headsign",
    "short_name",
    "direction",
    "block_id",
    "dataset",
)
STOP_TIME_CSV_FIELDS = (
    "trip_id",
    "arrival_time",
    "departure_time",
    "stop_id",
    "stop_sequence",
    "stop_headsign",
    "pickup_type",
    "drop_off_type",
    "timepoint",
)
STOP_TIME_COPY_COLUMNS = (
    "trip_id",
    "arrival_time",
    "departure_time",
    "stop_id",
    "stop_sequence",
    "stop_headsign",
    "pickup_type",
    "dropoff_type",
    "timepoint",
    "dataset",
)
SHAPE_CSV_FIELDS = (
    "shape_id",
    "shape_pt_lat",
    "shape_pt_lon",
    "shape_pt_sequence",
    "shape_dist_traveled",
)
SHAPE_COPY_COLUMNS = ("shape_id", "lat", "lon", "sequence", "distance", "dataset")

progress_columns = (
    rp.SpinnerColumn(finished_text="✅"),
    "[progress.description]{task.description}",
    rp.BarColumn(),
    rp.MofNCompleteColumn(),
    rp.TaskProgressColumn(),
    "|| Taken:",
    rp.TimeElapsedColumn(),
)


class ClearStrategy(Enum):
    DELETE = "delete"
    TRUNCATE = "truncate"
    TRUNCATE_CASCADE = "truncate_cascade"


def choose_clear_strategy(*, other_dataset_exists: bool, table_name: str) -> ClearStrategy:
    if other_dataset_exists:
        return ClearStrategy.DELETE
    if table_name in TRUNCATE_CASCADE_TABLES:
        return ClearStrategy.TRUNCATE_CASCADE
    return ClearStrategy.TRUNCATE


def optional_int(value: str) -> int | None:
    return None if value == "" else int(value)


def optional_float(value: str) -> float | None:
    return None if value == "" else float(value)


def csv_column_indexes(header: Sequence[str], names: tuple[str, ...]) -> dict[str, int]:
    resolved = list(header)
    if resolved:
        resolved[0] = resolved[0].lstrip("\ufeff")
    missing = [name for name in names if name not in resolved]
    if missing:
        msg = f"GTFS file missing required column(s): {', '.join(missing)}"
        raise ValueError(msg)
    return {name: resolved.index(name) for name in names}


def trip_record(row: list[str], col: dict[str, int], dataset: str) -> tuple:
    return (
        row[col["trip_id"]],
        row[col["route_id"]],
        row[col["service_id"]],
        row[col["shape_id"]],
        row[col["trip_headsign"]],
        row[col["trip_short_name"]],
        int(row[col["direction_id"]]),
        row[col["block_id"]],
        dataset,
    )


def stop_time_record(row: list[str], col: dict[str, int], dataset: str) -> tuple:
    return (
        row[col["trip_id"]],
        tdc.convert_29_hours_to_24_hours(row[col["arrival_time"]]),
        tdc.convert_29_hours_to_24_hours(row[col["departure_time"]]),
        row[col["stop_id"]],
        int(row[col["stop_sequence"]]),
        row[col["stop_headsign"]],
        optional_int(row[col["pickup_type"]]),
        optional_int(row[col["drop_off_type"]]),
        optional_int(row[col["timepoint"]]),
        dataset,
    )


def records_with_ids(rows: list[tuple], first_id: int) -> list[tuple]:
    return [(first_id + i, *row) for i, row in enumerate(rows)]


async def reserve_id_range(asyncpg_conn: Any, sequence_name: str, count: int) -> int:
    """Reserve ``count`` values from ``sequence_name`` and return the first id."""
    last = await asyncpg_conn.fetchval(
        f"SELECT setval('{sequence_name}', nextval('{sequence_name}') + $1 - 1)",
        count,
    )
    return last - count + 1


def shape_record(row: list[str], col: dict[str, int], dataset: str) -> tuple:
    return (
        row[col["shape_id"]],
        float(row[col["shape_pt_lat"]]),
        float(row[col["shape_pt_lon"]]),
        int(row[col["shape_pt_sequence"]]),
        optional_float(row[col["shape_dist_traveled"]]),
        dataset,
    )


class AsyncImporter(ABC):
    model: ClassVar[type]

    def __init__(
        self,
        reader: Iterator[dict[str, Any]],
        row_count: int | None,
        dataset: str,
        file_path: str | None = None,
    ):
        self.reader = reader
        self.row_count = row_count
        self.dataset = dataset
        self.file_path = file_path
        self.rows_imported = 0

    @abstractmethod
    def __str__(self) -> str:
        pass

    @abstractmethod
    async def import_data(self):
        pass

    async def clear_table(self) -> None:
        table_name = self.model.__tablename__
        async with async_session_factory() as session:
            other = await session.execute(
                select(self.model.dataset).where(self.model.dataset != self.dataset).limit(1)
            )
            strategy = choose_clear_strategy(
                other_dataset_exists=other.scalar_one_or_none() is not None,
                table_name=table_name,
            )
            if strategy is ClearStrategy.DELETE:
                await session.execute(delete(self.model).where(self.model.dataset == self.dataset))
            elif strategy is ClearStrategy.TRUNCATE_CASCADE:
                await session.execute(text(f'TRUNCATE TABLE "{table_name}" RESTART IDENTITY CASCADE'))
            else:
                await session.execute(text(f'TRUNCATE TABLE "{table_name}" RESTART IDENTITY'))
            await session.commit()


async def consumer(q: asyncio.Queue) -> None:
    async with async_session_factory() as session:
        while True:
            batch = await q.get()

            if batch is None:
                break

            session.add_all(batch)
            await session.commit()
            q.task_done()


def create_queue_and_tasks(producer) -> list[asyncio.Task]:
    """Creates a queue and tasks for producers and consumers"""

    q = asyncio.Queue(maxsize=QUEUE_MAXSIZE)
    producer_task = asyncio.create_task(producer(q, NUMBER_OF_CONSUMERS))
    consumer_tasks = [asyncio.create_task(consumer(q)) for _ in range(NUMBER_OF_CONSUMERS)]

    return consumer_tasks + [producer_task]


def get_importer_for_file(
    file: str,
    reader: Iterator[dict[str, Any]],
    row_count: int | None,
    dataset: str,
    file_path: str | None = None,
) -> AsyncImporter:
    """Maps a file name to the appropriate importer class"""

    map_file_to_importer = {
        "agency.txt": AgencyImporter,
        "calendar.txt": CalendarImporter,
        "calendar_dates.txt": CalendarDateImporter,
        "routes.txt": RouteImporter,
        "stops.txt": StopImporter,
        "trips.txt": TripImporter,
        "shapes.txt": ShapeImporter,
        "stop_times.txt": StopTimeImporter,
    }
    try:
        importer_class = map_file_to_importer[file]
    except KeyError as err:
        raise ValueError(f"File '{file}' does not have a supported importer.") from err
    return importer_class(reader, row_count, dataset, file_path=file_path)


class GTFSImporter:
    def __init__(self, filename: str, path: str):
        self.path = path
        self.filename = filename

    def get_reader(self) -> Iterator[dict[str, Any]]:
        """Returns a DictReader object for the file"""

        with open(self.path + self.filename, encoding="utf8") as f:
            reader = csv.DictReader(f)
            yield from reader

    def get_row_count(self):
        """Returns the number of rows in the file"""

        with rp.open(
            self.path + self.filename,
            "r",
            encoding="utf8",
            description=f"Reading {self.filename}",
            transient=True,
        ) as f:
            reader = csv.reader(f)
            next(reader)  # Skip the header row
            return sum(1 for _ in reader)

    def file_path(self) -> str:
        return self.path + self.filename


class OrmBatchImporter(AsyncImporter):
    progress_label: ClassVar[str]
    batchsize: ClassVar[int] = 10_000

    def __str__(self) -> str:
        return type(self).__name__

    @abstractmethod
    def build_model(self, row: dict[str, Any]):
        pass

    async def import_data(self):
        tasks = create_queue_and_tasks(self.producer)
        await asyncio.gather(*tasks)

    async def producer(self, q: asyncio.Queue, number_of_consumers: int):
        batch_count = 0
        objects_to_commit = []

        with rp.Progress(*progress_columns) as progress:
            task = progress.add_task(f"[green]{self.progress_label}", total=self.row_count)

            for row in self.reader:
                objects_to_commit.append(self.build_model(row))
                batch_count += 1
                self.rows_imported += 1
                progress.update(task, advance=1)

                if batch_count >= self.batchsize:
                    await q.put(objects_to_commit)
                    objects_to_commit = []
                    batch_count = 0

            if objects_to_commit:
                await q.put(objects_to_commit)

            for _ in range(number_of_consumers):
                await q.put(None)


class CopyImporter(AsyncImporter):
    table_name: ClassVar[str]
    csv_fields: ClassVar[tuple[str, ...]]
    copy_columns: ClassVar[tuple[str, ...]]
    progress_label: ClassVar[str]
    id_sequence: ClassVar[str | None] = None
    batchsize: ClassVar[int] = COPY_BATCH_SIZE

    def __str__(self) -> str:
        return type(self).__name__

    @abstractmethod
    def record_from_row(self, row: list[str], col: dict[str, int]) -> tuple:
        pass

    async def import_data(self):
        if not self.file_path:
            msg = f"{self} requires a file path for COPY"
            raise ValueError(msg)

        try:
            await drop_secondary_indexes(self.table_name)
            await self._copy_file()
        finally:
            await create_secondary_indexes(self.table_name)

    async def _copy_file(self) -> None:
        engine = get_async_engine()
        async with engine.connect() as conn:
            raw = await conn.get_raw_connection()
            asyncpg_conn = raw.driver_connection
            if asyncpg_conn is None:
                msg = "Could not get asyncpg connection for COPY"
                raise RuntimeError(msg)

            file_path = self.file_path
            if file_path is None:
                msg = f"{self} requires a file path for COPY"
                raise ValueError(msg)

            batch: list[tuple] = []
            with open(file_path, encoding="utf8") as f:
                reader = csv.reader(f)
                col = csv_column_indexes(next(reader), self.csv_fields)

                with rp.Progress(*progress_columns) as progress:
                    task = progress.add_task(f"[green]{self.progress_label}", total=self.row_count)

                    for row in reader:
                        batch.append(self.record_from_row(row, col))
                        self.rows_imported += 1

                        if len(batch) >= self.batchsize:
                            await self._copy_batch(asyncpg_conn, conn, batch)
                            progress.update(task, advance=len(batch))
                            batch = []

                    if batch:
                        await self._copy_batch(asyncpg_conn, conn, batch)
                        progress.update(task, advance=len(batch))

    async def _copy_batch(self, asyncpg_conn: Any, conn: Any, batch: list[tuple]) -> None:
        columns = self.copy_columns
        records: list[tuple] = batch
        if self.id_sequence is not None:
            first_id = await reserve_id_range(asyncpg_conn, self.id_sequence, len(batch))
            records = records_with_ids(batch, first_id)
            columns = ("id", *self.copy_columns)
        await asyncpg_conn.copy_records_to_table(
            self.table_name,
            records=records,
            columns=columns,
        )
        await conn.commit()


class AgencyImporter(OrmBatchImporter):
    model = AgencyModel
    progress_label = "Importing Agencies..."

    def build_model(self, row: dict[str, Any]) -> AgencyModel:
        return AgencyModel(
            id=row["agency_id"],
            name=row["agency_name"],
            url=row["agency_url"],
            timezone=row["agency_timezone"],
            dataset=self.dataset,
        )


class CalendarImporter(OrmBatchImporter):
    model = CalendarModel
    progress_label = "Importing Calendars..."

    def build_model(self, row: dict[str, Any]) -> CalendarModel:
        return CalendarModel(
            id=row["service_id"],
            monday=int(row["monday"]),
            tuesday=int(row["tuesday"]),
            wednesday=int(row["wednesday"]),
            thursday=int(row["thursday"]),
            friday=int(row["friday"]),
            saturday=int(row["saturday"]),
            sunday=int(row["sunday"]),
            start_date=tdc.convert_joined_date_to_date(row["start_date"]),
            end_date=tdc.convert_joined_date_to_date(row["end_date"]),
            dataset=self.dataset,
        )


class CalendarDateImporter(OrmBatchImporter):
    model = CalendarDateModel
    progress_label = "Importing Calendar Dates..."

    def build_model(self, row: dict[str, Any]) -> CalendarDateModel:
        if row["exception_type"] == "1":
            exception_type = "added"
        elif row["exception_type"] == "2":
            exception_type = "removed"
        else:
            raise ValueError(f"Invalid exception_type '{row['exception_type']}'")

        return CalendarDateModel(
            service_id=row["service_id"],
            date=tdc.convert_joined_date_to_date(row["date"]),
            exception_type=exception_type,
            dataset=self.dataset,
        )


class RouteImporter(OrmBatchImporter):
    model = RouteModel
    progress_label = "Importing Routes..."

    def build_model(self, row: dict[str, Any]) -> RouteModel:
        return RouteModel(
            id=row["route_id"],
            agency_id=row["agency_id"],
            short_name=row["route_short_name"],
            long_name=row["route_long_name"],
            description=row["route_desc"],
            route_type=RouteType(int(row["route_type"])),
            url=row["route_url"],
            color=row["route_color"],
            text_color=row["route_text_color"],
            dataset=self.dataset,
        )


class StopImporter(OrmBatchImporter):
    model = StopModel
    progress_label = "Importing Stops..."

    def build_model(self, row: dict[str, Any]) -> StopModel:
        return StopModel(
            id=row["stop_id"],
            code=row["stop_code"],
            name=row["stop_name"],
            description=row["stop_desc"],
            lat=float(row["stop_lat"]),
            lon=float(row["stop_lon"]),
            zone_id=row["zone_id"],
            url=row["stop_url"],
            location_type=optional_int(row["location_type"]),
            parent_station=row["parent_station"] or None,
            dataset=self.dataset,
        )


class TripImporter(CopyImporter):
    model = TripModel
    table_name = "trip"
    csv_fields = TRIP_CSV_FIELDS
    copy_columns = TRIP_COPY_COLUMNS
    progress_label = "Importing Trips..."

    def record_from_row(self, row: list[str], col: dict[str, int]) -> tuple:
        return trip_record(row, col, self.dataset)


class ShapeImporter(CopyImporter):
    model = ShapeModel
    table_name = "shape"
    csv_fields = SHAPE_CSV_FIELDS
    copy_columns = SHAPE_COPY_COLUMNS
    progress_label = "Importing Shapes..."
    id_sequence = "shape_id_seq"

    def record_from_row(self, row: list[str], col: dict[str, int]) -> tuple:
        return shape_record(row, col, self.dataset)


class StopTimeImporter(CopyImporter):
    model = StopTimeModel
    table_name = "stop_time"
    csv_fields = STOP_TIME_CSV_FIELDS
    copy_columns = STOP_TIME_COPY_COLUMNS
    progress_label = "Importing Stop Times..."
    id_sequence = "stop_time_id_seq"

    def record_from_row(self, row: list[str], col: dict[str, int]) -> tuple:
        return stop_time_record(row, col, self.dataset)
