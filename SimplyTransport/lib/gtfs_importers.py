import asyncio
import csv
from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

import rich.progress as rp
from sqlalchemy import insert

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
from .db.database import async_session_factory, get_sync_session

NUMBER_OF_CONSUMERS = 2
QUEUE_MAXSIZE = 2

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


@dataclass(frozen=True, slots=True)
class GTFSCoreBatch:
    """Marker payload for PostgreSQL/Core bulk insert (stop_time, shape)."""

    table: Literal["stop_time", "shape"]
    rows: list[dict[str, Any]]


class AsyncImporter(ABC):
    def __init__(self, reader: Iterator[dict[str, Any]], row_count: int | None, dataset: str):
        self.reader = reader
        self.row_count = row_count
        self.dataset = dataset
        self.rows_imported = 0

    @abstractmethod
    def __str__(self) -> str:
        pass

    @abstractmethod
    async def import_data(self):
        pass

    @abstractmethod
    async def producer(self, q: asyncio.Queue, number_of_consumers: int):
        pass

    @abstractmethod
    def clear_table(self):
        pass


async def consumer(q: asyncio.Queue) -> None:
    async with async_session_factory() as session:
        while True:
            batch = await q.get()

            if batch is None:
                break

            if isinstance(batch, GTFSCoreBatch):
                if batch.table == "stop_time":
                    await session.execute(insert(StopTimeModel), batch.rows)
                elif batch.table == "shape":
                    await session.execute(insert(ShapeModel), batch.rows)
                else:
                    msg = f"Unknown GTFS core batch table: {batch.table}"
                    raise ValueError(msg)
                await session.commit()
            else:
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
    file: str, reader: Iterator[dict[str, Any]], row_count: int | None, dataset: str
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
    importer = importer_class(reader, row_count, dataset)
    return importer


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


class AgencyImporter(AsyncImporter):
    def __init__(self, reader: Iterator[dict[str, Any]], row_count: int | None, dataset: str):
        super().__init__(reader, row_count, dataset)
        self.batchsize = 10000

    def __str__(self) -> str:
        return "AgencyImporter"

    async def import_data(self):
        tasks = create_queue_and_tasks(self.producer)
        await asyncio.gather(*tasks)

    async def producer(self, q: asyncio.Queue, number_of_consumers: int):
        batch_count = 0
        objects_to_commit = []

        with rp.Progress(*progress_columns) as progress:
            task = progress.add_task("[green]Importing Agencies...", total=self.row_count)

            for row in self.reader:
                new_agency = AgencyModel(
                    id=row["agency_id"],
                    name=row["agency_name"],
                    url=row["agency_url"],
                    timezone=row["agency_timezone"],
                    dataset=self.dataset,
                )

                objects_to_commit.append(new_agency)
                batch_count += 1
                self.rows_imported += 1
                progress.update(task, advance=1)

                if batch_count >= self.batchsize:
                    await q.put(objects_to_commit)
                    objects_to_commit = []
                    batch_count = 0

            if objects_to_commit:
                await q.put(objects_to_commit)

            # Signal the consumer that the producer is done
            for _ in range(number_of_consumers):
                await q.put(None)

    def clear_table(self):
        """Clears the table in the database that corresponds to the file"""

        with get_sync_session() as session:
            session.query(AgencyModel).filter(AgencyModel.dataset == self.dataset).delete()
            session.commit()


class CalendarImporter(AsyncImporter):
    def __init__(
        self,
        reader: Iterator[dict[str, Any]],
        row_count: int | None,
        dataset: str,
    ):
        super().__init__(reader, row_count, dataset)
        self.batchsize = 10000

    def __str__(self) -> str:
        return "CalendarImporter"

    async def import_data(self):
        tasks = create_queue_and_tasks(self.producer)
        await asyncio.gather(*tasks)

    async def producer(self, q: asyncio.Queue, number_of_consumers: int):
        batch_count = 0
        objects_to_commit = []

        with rp.Progress(*progress_columns) as progress:
            task = progress.add_task("[green]Importing Calendars...", total=self.row_count)

            for row in self.reader:
                new_calendar = CalendarModel(
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

                objects_to_commit.append(new_calendar)
                batch_count += 1
                self.rows_imported += 1
                progress.update(task, advance=1)

                if batch_count >= self.batchsize:
                    await q.put(objects_to_commit)
                    objects_to_commit = []
                    batch_count = 0

            if objects_to_commit:
                await q.put(objects_to_commit)

            # Signal the consumer that the producer is done
            for _ in range(number_of_consumers):
                await q.put(None)

    def clear_table(self):
        """Clears the table in the database that corresponds to the file"""

        with get_sync_session() as session:
            session.query(CalendarModel).filter(CalendarModel.dataset == self.dataset).delete()
            session.commit()


class CalendarDateImporter(AsyncImporter):
    def __init__(self, reader: Iterator[dict[str, Any]], row_count: int | None, dataset: str):
        super().__init__(reader, row_count, dataset)
        self.batchsize = 10000

    def __str__(self) -> str:
        return "CalendarDateImporter"

    async def import_data(self):
        tasks = create_queue_and_tasks(self.producer)
        await asyncio.gather(*tasks)

    async def producer(self, q: asyncio.Queue, number_of_consumers: int):
        batch_count = 0
        objects_to_commit = []

        with rp.Progress(*progress_columns) as progress:
            task = progress.add_task("[green]Importing Calendar Dates...", total=self.row_count)

            for row in self.reader:
                if row["exception_type"] == "1":
                    exception_type = "added"
                elif row["exception_type"] == "2":
                    exception_type = "removed"
                else:
                    raise ValueError(f"Invalid exception_type '{row['exception_type']}'")

                new_calendar_date = CalendarDateModel(
                    service_id=row["service_id"],
                    date=tdc.convert_joined_date_to_date(row["date"]),
                    exception_type=exception_type,
                    dataset=self.dataset,
                )

                objects_to_commit.append(new_calendar_date)
                batch_count += 1
                self.rows_imported += 1
                progress.update(task, advance=1)

                if batch_count >= self.batchsize:
                    await q.put(objects_to_commit)
                    objects_to_commit = []
                    batch_count = 0

            if objects_to_commit:
                await q.put(objects_to_commit)

            # Signal the consumer that the producer is done
            for _ in range(number_of_consumers):
                await q.put(None)

    def clear_table(self):
        """Clears the table in the database that corresponds to the file"""

        with get_sync_session() as session:
            session.query(CalendarDateModel).filter(CalendarDateModel.dataset == self.dataset).delete()
            session.commit()


class RouteImporter(AsyncImporter):
    def __init__(self, reader: Iterator[dict[str, Any]], row_count: int | None, dataset: str):
        super().__init__(reader, row_count, dataset)
        self.batchsize = 10000

    def __str__(self) -> str:
        return "RouteImporter"

    async def import_data(self):
        tasks = create_queue_and_tasks(self.producer)
        await asyncio.gather(*tasks)

    async def producer(self, q: asyncio.Queue, number_of_consumers: int):
        batch_count = 0
        objects_to_commit = []

        with rp.Progress(*progress_columns) as progress:
            task = progress.add_task("[green]Importing Routes...", total=self.row_count)

            for row in self.reader:
                route_type = RouteType(int(row["route_type"]))

                new_route = RouteModel(
                    id=row["route_id"],
                    agency_id=row["agency_id"],
                    short_name=row["route_short_name"],
                    long_name=row["route_long_name"],
                    description=row["route_desc"],
                    route_type=route_type,
                    url=row["route_url"],
                    color=row["route_color"],
                    text_color=row["route_text_color"],
                    dataset=self.dataset,
                )

                objects_to_commit.append(new_route)
                batch_count += 1
                self.rows_imported += 1
                progress.update(task, advance=1)

                if batch_count >= self.batchsize:
                    await q.put(objects_to_commit)
                    objects_to_commit = []
                    batch_count = 0

            if objects_to_commit:
                await q.put(objects_to_commit)

            # Signal the consumer that the producer is done
            for _ in range(number_of_consumers):
                await q.put(None)

    def clear_table(self):
        """Clears the table in the database that corresponds to the file"""

        with get_sync_session() as session:
            session.query(RouteModel).filter(RouteModel.dataset == self.dataset).delete()
            session.commit()


class TripImporter(AsyncImporter):
    def __init__(self, reader: Iterator[dict[str, Any]], row_count: int | None, dataset: str):
        super().__init__(reader, row_count, dataset)
        self.batchsize = 20000

    def __str__(self) -> str:
        return "TripImporter"

    async def import_data(self):
        tasks = create_queue_and_tasks(self.producer)
        await asyncio.gather(*tasks)

    async def producer(self, q: asyncio.Queue, number_of_consumers: int):
        batch_count = 0
        objects_to_commit = []

        with rp.Progress(*progress_columns) as progress:
            task = progress.add_task("[green]Importing Trips...", total=self.row_count)

            for row in self.reader:
                new_trip = TripModel(
                    id=row["trip_id"],
                    route_id=row["route_id"],
                    service_id=row["service_id"],
                    shape_id=row["shape_id"],
                    headsign=row["trip_headsign"],
                    short_name=row["trip_short_name"],
                    direction=int(row["direction_id"]),
                    block_id=row["block_id"],
                    dataset=self.dataset,
                )

                objects_to_commit.append(new_trip)
                batch_count += 1
                self.rows_imported += 1
                progress.update(task, advance=1)

                if batch_count >= self.batchsize:
                    await q.put(objects_to_commit)
                    objects_to_commit = []
                    batch_count = 0

            if objects_to_commit:
                await q.put(objects_to_commit)

            # Signal the consumer that the producer is done
            for _ in range(number_of_consumers):
                await q.put(None)

    def clear_table(self):
        """Clears the table in the database that corresponds to the file"""

        with get_sync_session() as session:
            session.query(TripModel).filter(TripModel.dataset == self.dataset).delete()
            session.commit()


class StopImporter(AsyncImporter):
    def __init__(self, reader: Iterator[dict[str, Any]], row_count: int | None, dataset: str):
        super().__init__(reader, row_count, dataset)
        self.batchsize = 10000

    def __str__(self) -> str:
        return "StopImporter"

    async def import_data(self):
        tasks = create_queue_and_tasks(self.producer)
        await asyncio.gather(*tasks)

    async def producer(self, q: asyncio.Queue, number_of_consumers: int):
        batch_count = 0
        objects_to_commit = []

        with rp.Progress(*progress_columns) as progress:
            task = progress.add_task("[green]Importing Stops...", total=self.row_count)

            for row in self.reader:
                if row["location_type"] == "":
                    location_type = None
                else:
                    location_type = int(row["location_type"])

                if row["parent_station"] == "":
                    parent_station = None
                else:
                    parent_station = row["parent_station"]

                new_stop = StopModel(
                    id=row["stop_id"],
                    code=row["stop_code"],
                    name=row["stop_name"],
                    description=row["stop_desc"],
                    lat=float(row["stop_lat"]),
                    lon=float(row["stop_lon"]),
                    zone_id=row["zone_id"],
                    url=row["stop_url"],
                    location_type=location_type,
                    parent_station=parent_station,
                    dataset=self.dataset,
                )

                objects_to_commit.append(new_stop)
                batch_count += 1
                self.rows_imported += 1
                progress.update(task, advance=1)

                if batch_count >= self.batchsize:
                    await q.put(objects_to_commit)
                    objects_to_commit = []
                    batch_count = 0

            if objects_to_commit:
                await q.put(objects_to_commit)

            # Signal the consumer that the producer is done
            for _ in range(number_of_consumers):
                await q.put(None)

    def clear_table(self):
        """Clears the table in the database that corresponds to the file"""

        with get_sync_session() as session:
            session.query(StopModel).filter(StopModel.dataset == self.dataset).delete()
            session.commit()


class ShapeImporter(AsyncImporter):
    def __init__(self, reader: Iterator[dict[str, Any]], row_count: int | None, dataset: str):
        super().__init__(reader, row_count, dataset)
        self.batchsize = 20000

    def __str__(self) -> str:
        return "ShapeImporter"

    async def import_data(self):
        tasks = create_queue_and_tasks(self.producer)
        await asyncio.gather(*tasks)

    async def producer(self, q: asyncio.Queue, number_of_consumers: int):
        batch_dicts: list[dict[str, Any]] = []

        with rp.Progress(*progress_columns) as progress:
            task = progress.add_task("[green]Importing Shapes...", total=self.row_count)

            for row in self.reader:
                if not batch_dicts:
                    stamp = datetime.now(UTC)
                batch_dicts.append(
                    {
                        "shape_id": row["shape_id"],
                        "lat": float(row["shape_pt_lat"]),
                        "lon": float(row["shape_pt_lon"]),
                        "sequence": int(row["shape_pt_sequence"]),
                        "distance": float(row["shape_dist_traveled"])
                        if row["shape_dist_traveled"] != ""
                        else None,
                        "dataset": self.dataset,
                        "created_at": stamp,
                        "updated_at": stamp,
                    }
                )
                self.rows_imported += 1

                if len(batch_dicts) >= self.batchsize:
                    await q.put(GTFSCoreBatch("shape", batch_dicts))
                    progress.update(task, advance=len(batch_dicts))
                    batch_dicts = []

            if batch_dicts:
                await q.put(GTFSCoreBatch("shape", batch_dicts))
                progress.update(task, advance=len(batch_dicts))

            # Signal the consumer that the producer is done
            for _ in range(number_of_consumers):
                await q.put(None)

    def clear_table(self):
        """Clears the table in the database that corresponds to the file"""

        with get_sync_session() as session:
            session.query(ShapeModel).filter(ShapeModel.dataset == self.dataset).delete()
            session.commit()


class StopTimeImporter(AsyncImporter):
    def __init__(self, reader: Iterator[dict[str, Any]], row_count: int | None, dataset: str):
        super().__init__(reader, row_count, dataset)
        self.batchsize = 20000

    def __str__(self) -> str:
        return "StopTimeImporter"

    async def import_data(self):
        tasks = create_queue_and_tasks(self.producer)
        await asyncio.gather(*tasks)

    async def producer(self, q: asyncio.Queue, number_of_consumers: int):
        batch_dicts: list[dict[str, Any]] = []

        with rp.Progress(*progress_columns) as progress:
            task = progress.add_task("[green]Importing Stop Times...", total=self.row_count)

            for row in self.reader:
                arrival_time = tdc.convert_29_hours_to_24_hours(row["arrival_time"])
                departure_time = tdc.convert_29_hours_to_24_hours(row["departure_time"])

                if row["pickup_type"] == "":
                    pickup_type = None
                else:
                    pickup_type = int(row["pickup_type"])

                if row["drop_off_type"] == "":
                    drop_off_type = None
                else:
                    drop_off_type = int(row["drop_off_type"])

                if row["timepoint"] == "":
                    timepoint = None
                else:
                    timepoint = int(row["timepoint"])

                if not batch_dicts:
                    stamp = datetime.now(UTC)
                batch_dicts.append(
                    {
                        "trip_id": row["trip_id"],
                        "arrival_time": arrival_time,
                        "departure_time": departure_time,
                        "stop_id": row["stop_id"],
                        "stop_sequence": int(row["stop_sequence"]),
                        "stop_headsign": row["stop_headsign"],
                        "pickup_type": pickup_type,
                        "dropoff_type": drop_off_type,
                        "timepoint": timepoint,
                        "dataset": self.dataset,
                        "created_at": stamp,
                        "updated_at": stamp,
                    }
                )
                self.rows_imported += 1

                if len(batch_dicts) >= self.batchsize:
                    await q.put(GTFSCoreBatch("stop_time", batch_dicts))
                    progress.update(task, advance=len(batch_dicts))
                    batch_dicts = []

            if batch_dicts:
                await q.put(GTFSCoreBatch("stop_time", batch_dicts))
                progress.update(task, advance=len(batch_dicts))

            # Signal the consumer that the producer is done
            for _ in range(number_of_consumers):
                await q.put(None)

    def clear_table(self):
        """Clears the table in the database that corresponds to the file"""

        with get_sync_session() as session:
            session.query(StopTimeModel).filter(StopTimeModel.dataset == self.dataset).delete()
            session.commit()
