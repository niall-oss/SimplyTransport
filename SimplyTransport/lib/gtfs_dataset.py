import os
import time
from pathlib import Path

import rich.progress as rp
import SimplyTransport.lib.gtfs_importers as imp
from rich.console import Console
from SimplyTransport.domain.events.event_repo import create_event_with_session
from SimplyTransport.domain.events.event_types import EventType
from SimplyTransport.domain.services.statistics_service import provide_statistics_service
from SimplyTransport.lib.cache import provide_redis_service
from SimplyTransport.lib.cache_keys import CacheKeys
from SimplyTransport.lib.db.database import async_session_factory
from SimplyTransport.lib.db.timescale_database import async_timescale_session_factory
from SimplyTransport.lib.logging.logging import provide_logger

logger = provide_logger(__name__)

FILES_TO_IMPORT = [
    "agency.txt",
    "calendar.txt",
    "calendar_dates.txt",
    "routes.txt",
    "stops.txt",
    "trips.txt",
    "stop_times.txt",
    "shapes.txt",
]


def normalize_gtfs_directory(directory: str) -> str:
    directory = directory.replace("\\", "/")
    if not directory.endswith("/"):
        directory += "/"
    return directory


def gtfs_dataset_label_from_import_dir(import_dir: str) -> str:
    """Dataset tag stored on GTFS rows: the folder name that holds the .txt files."""
    return Path(import_dir).resolve().name


async def import_gtfs_dataset(directory: str) -> None:
    """Import GTFS static files from directory into the database."""
    console = Console()
    console.print("Importing GTFS data...")

    directory = normalize_gtfs_directory(directory)
    dataset = gtfs_dataset_label_from_import_dir(directory)

    attributes_of_total_rows = {}
    total_time_taken = 0.0
    start = time.perf_counter()

    with rp.Progress(
        rp.SpinnerColumn(finished_text="✅"),
        "[progress.description]{task.description}",
        rp.TimeElapsedColumn(),
    ) as progress:
        task = progress.add_task("[red]Clearing realtime tables...", total=1)
        await imp.clear_realtime_tables()
        progress.update(task, advance=1)

    for file in FILES_TO_IMPORT:
        file_start = time.perf_counter()
        if not (os.path.exists(directory) and os.path.isfile(directory + file)):
            console.print(f"[red]Error: File '{file}' does not exist. Skipping...")
            attributes_of_total_rows[file.replace(".txt", "")] = {
                "time_taken(s)": 0,
                "row_count": 0,
                "error": f"File '{file}' does not exist.",
            }
            continue

        generic_importer = imp.GTFSImporter(file, directory)
        reader = generic_importer.get_reader()
        try:
            importer = imp.get_importer_for_file(
                file, reader, None, dataset, file_path=generic_importer.file_path()
            )
        except ValueError:
            console.print(f"\n[red]Error: File '{file}' does not have a supported importer. Skipping...")
            attributes_of_total_rows[file.replace(".txt", "")] = {
                "time_taken(s)": 0,
                "row_count": 0,
                "error": f"File '{file}' does not have a supported importer.",
            }
            continue

        with rp.Progress(
            rp.SpinnerColumn(finished_text="✅"),
            "[progress.description]{task.description}",
            rp.TimeElapsedColumn(),
        ) as progress:
            task = progress.add_task("[red]Clearing database table...", total=1)
            await importer.clear_table()
            progress.update(task, advance=1)

        await importer.import_data()

        file_finish = time.perf_counter()
        time_taken = round(file_finish - file_start, 2)
        total_time_taken += time_taken
        row_count = importer.rows_imported
        console.print(f"[green]Imported {row_count} rows from {file}")

        attributes_of_total_rows[file.replace(".txt", "")] = {
            "time_taken(s)": time_taken,
            "row_count": row_count,
        }

    attributes = {
        "dataset": dataset,
        "totals": attributes_of_total_rows,
        "total_time_taken(s)": round(total_time_taken, 2),
    }

    await create_event_with_session(
        EventType.GTFS_DATABASE_UPDATED,
        "GTFS static data updated with latest schedules",
        attributes,
    )

    async with await provide_redis_service() as redis_service:
        await redis_service.delete_keys_by_pattern(CacheKeys.StopMaps.STOP_MAP_DELETE_ALL_KEY_TEMPLATE)
        await redis_service.delete_keys_by_pattern(CacheKeys.StopMaps.STOP_MAP_NEARBY_DELETE_ALL_KEY_TEMPLATE)
        await redis_service.delete_keys_by_pattern(CacheKeys.RouteMaps.ROUTE_MAP_DELETE_ALL_KEY_TEMPLATE)
        await redis_service.delete_keys_by_pattern(CacheKeys.Schedules.SCHEDULE_DELETE_ALL_KEY_TEMPLATE)
        await redis_service.delete_keys_by_pattern(
            CacheKeys.StaticMaps.STATIC_MAP_AGENCY_ROUTE_DELETE_ALL_KEY_TEMPLATE
        )
        await redis_service.delete_keys_by_pattern(
            CacheKeys.StaticMaps.STATIC_MAP_STOP_DELETE_ALL_KEY_TEMPLATE
        )
        await redis_service.delete_keys_by_pattern(CacheKeys.StopApi.DETAILED_DELETE_ALL_KEY_TEMPLATE)
        await redis_service.delete_keys_by_pattern(CacheKeys.RealTime.REALTIME_ROUTE_DELETE_ALL_KEY_TEMPLATE)

    finish = time.perf_counter()
    console.print(f"\n[blue]Finished import in {round(finish - start, 2)} second(s)")


async def generate_database_statistics() -> float:
    """Compute and store GTFS statistics, then record an event. Returns seconds taken."""
    start = time.perf_counter()

    async with async_timescale_session_factory() as timescale_session:
        async with async_session_factory() as session:
            statistics_service = await provide_statistics_service(
                db_session=session,
                timescale_db_session=timescale_session,
            )
            await statistics_service.update_all_statistics()

    async with await provide_redis_service() as redis_service:
        await redis_service.delete_keys_by_pattern(CacheKeys.Statistics.STATISTICS_DELETE_ALL_KEY_TEMPLATE)

    time_taken = round(time.perf_counter() - start, 2)
    await create_event_with_session(
        EventType.DATABASE_STATISTICS_UPDATED,
        "Statistics generated for the database",
        {"time_taken(s)": time_taken},
    )
    logger.info(f"Finished generating statistics in {time_taken} second(s)")
    return time_taken
