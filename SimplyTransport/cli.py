import asyncio
import functools
import json
import os
import time
from pathlib import Path

import click
import geojson
import rich.progress as rp
from litestar import Litestar
from litestar.plugins import CLIPluginProtocol
from rich.console import Console
from rich.table import Table

from SimplyTransport.lib.db import services as db_services

from .domain.events.event_repo import create_event_with_session, provide_event_repo
from .domain.events.event_types import EventType
from .lib import settings as lib_settings
from .lib.cache import provide_redis_service
from .lib.cache_keys import CacheKeys
from .lib.concurrency import concurrency, release_lock, skip_if_lock_held, try_acquire_lock
from .lib.db.database import async_session_factory
from .lib.db.timescale_database import async_timescale_session_factory
from .lib.gtfs_realtime_importers import (
    RealTimeImporter,
    RealTimeVehiclesImporter,
    asyncio_gather_imports,
    progress_columns,
)
from .lib.logging.logging import provide_logger
from .lib.realtime_seed_time_shift import shift_db_stop_times_and_patch_payload_for_now
from .lib.stop_features_importer import StopFeaturesImporter
from .lib.tracing import cli_command_span, cli_span_name, get_app_tracer
from .timescale.services.delays_service import provide_delays_service

DEFAULT_GTFS_DIRECTORY = "./gtfs_data/TFI/"

# Redis CLI mutex: static GTFS import vs realtime / delays jobs
_CLI_LOCK_GTFS_STATIC_IMPORT = "gtfs_static_import"
_CLI_LOCK_GTFS_STATIC_IMPORT_TTL_S = 4 * 60 * 60

logger = provide_logger(__name__)


def gtfs_directory_validator(directory: str | None, console: Console):
    if directory:
        if os.path.exists(directory) and os.path.isdir(directory):
            print("Using directory: " + directory)
        else:
            console.print(f"[red]Error: Directory '{directory}' does not exist.")
            raise click.Abort()
    else:
        directory = DEFAULT_GTFS_DIRECTORY
        console.print(f"No directory specified, using default of {directory}")

    return directory


def gtfs_dataset_label_from_import_dir(import_dir: str) -> str:
    """Dataset tag stored on GTFS rows: the folder name that holds the .txt files (e.g. .../TFI -> TFI)."""

    return Path(import_dir).resolve().name


# https://github.com/pallets/click/issues/2033
def make_sync(func):
    """Decorator to run async functions in a sync context"""

    tracer = get_app_tracer()

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        with tracer.start_as_current_span(cli_span_name(func)):
            return asyncio.run(func(*args, **kwargs))

    return wrapper


class CLIPlugin(CLIPluginProtocol):
    def on_cli_init(self, cli: click.Group) -> None:
        @cli.command(name="settings", help="Prints the current settings of the app")
        def settings():
            """Prints the current settings of the app"""

            with cli_command_span("cli.settings"):
                from SimplyTransport.lib import settings

                console = Console()

                table = Table()
                table.add_column("Setting", style="cyan")
                table.add_column("Value")

                table.add_row("LITESTAR_APP", settings.app.LITESTAR_APP)
                if settings.app.DEBUG:
                    debug_style = "green"
                else:
                    debug_style = "red"

                table.add_row("Debug", str(settings.app.DEBUG), style=debug_style)
                table.add_row("Environment", settings.app.ENVIRONMENT)
                table.add_row("Database URL", settings.app.DB_URL)
                table.add_row("Database Echo", str(settings.app.DB_ECHO))
                table.add_row("Log Level", settings.app.LOG_LEVEL)

                console.print(table)

        @cli.command(name="docs", help="Prints the documentation urls for the API")
        def docs(app: Litestar):
            """Prints the documentation urls for the API"""

            with cli_command_span("cli.docs"):
                console = Console()
                base_url = "http://localhost:8000"  # TODO: Make this automatically get the base url
                table = Table()
                table.add_column("Doc Type", style="cyan")
                table.add_column("URL")

                if app.openapi_config is None:
                    console.print("[red]Error: OpenAPI controller not found.")
                    return

                docs_path = app.openapi_config.path
                renderers = app.openapi_config.render_plugins

                table.add_row("Default", f"{base_url}{docs_path}")
                for renderer in renderers:
                    renderer_name = renderer.__class__.__name__.replace("RenderPlugin", "")
                    renderer_path = renderer.paths[0]
                    table.add_row(renderer_name, f"{base_url}{docs_path}{renderer_path}")

                console.print(table)

        @cli.command(name="importgtfs", help="Imports GTFS data into the database")
        @click.option("-dir", help="Override the directory containing the GTFS data to import")
        @click.option("--yes", is_flag=True, help="Skip the confirmation prompt")
        @make_sync
        async def importgtfs(dir: str, yes: bool):
            """Imports GTFS data into the database"""
            from SimplyTransport.lib.gtfs_dataset import import_gtfs_dataset

            console = Console()
            dir = gtfs_directory_validator(dir, console)
            dataset = gtfs_dataset_label_from_import_dir(dir)

            if not yes:
                response = click.prompt(
                    f"\nYou are about to import this dataset and assign it to '{dataset}'. "
                    "Press 'y' to continue, anything else to abort: ",
                    type=str,
                    default="",
                    show_default=False,
                )
                if response != "y":
                    console.print("[red]Aborting import...")
                    return

            lock = await try_acquire_lock(_CLI_LOCK_GTFS_STATIC_IMPORT, _CLI_LOCK_GTFS_STATIC_IMPORT_TTL_S)
            if lock is None:
                console.print(
                    "[yellow]Another GTFS static import is already in progress (Redis lock held). Aborting."
                )
                return
            lock_client, lock_token = lock

            try:
                await import_gtfs_dataset(dir)
            finally:
                await release_lock(lock_client, _CLI_LOCK_GTFS_STATIC_IMPORT, lock_token)

        @cli.command(name="importrealtime", help="Imports GTFS realtime data into the database")
        @click.option("-url", help="Override the default URL for the GTFS realtime data")
        @click.option("-apikey", help="Override the default API key for the GTFS realtime data")
        @click.option("-dataset", help="Override the default dataset that the data will be saved against")
        @make_sync
        @skip_if_lock_held(
            _CLI_LOCK_GTFS_STATIC_IMPORT,
            skip_message="Skipped: GTFS static import is in progress",
        )
        @concurrency(1)
        async def importrealtime(url: str, apikey: str, dataset: str):
            """Imports GTFS realtime data into the database"""

            start: float = time.perf_counter()
            console = Console()
            console.print("Importing GTFS realtime data...")

            from SimplyTransport.lib import settings

            if url:
                realtime_url = url
                console.print(f"\nOverriding URL: {realtime_url}")
            else:
                realtime_url = settings.app.GTFS_TFI_REALTIME_URL

            if apikey:
                realtime_apikey = apikey
                console.print(f"\nOverriding API key: {realtime_apikey}")
            else:
                realtime_apikey = settings.app.GTFS_TFI_API_KEY_1

            if dataset:
                realtime_dataset = dataset
                console.print(f"\nOverriding dataset: {realtime_dataset}")
            else:
                realtime_dataset = settings.app.GTFS_TFI_DATASET

            importer = RealTimeImporter(url=realtime_url, api_key=realtime_apikey, dataset=realtime_dataset)

            console.print(f"\nImporting using dataset: {realtime_dataset} from {realtime_url}")

            data = await importer.get_data()

            if data is None:
                console.print(
                    "[red]Error: No data returned from API, either response was not 200 or JSON was invalid."
                )
                return

            console.print(f"\n{len(data['entity'])} entities returned from API")

            with rp.Progress(*progress_columns) as progress:
                total_stop_times, total_trips = await asyncio_gather_imports(importer, data, progress)

            finish: float = time.perf_counter()
            attributes = {
                "dataset": realtime_dataset,
                "total_trips": total_trips,
                "total_stop_times": total_stop_times,
                "time_taken(s)": round(finish - start, 2),
            }
            await create_event_with_session(
                EventType.REALTIME_DATABASE_UPDATED,
                "Realtime database updated with new realtime information",
                attributes,
            )

            redis_service = await provide_redis_service()
            await redis_service.delete_keys_by_pattern(
                CacheKeys.RealTime.REALTIME_STOP_DELETE_ALL_KEY_TEMPLATE
            )
            await redis_service.delete_keys_by_pattern(
                CacheKeys.RealTime.REALTIME_STOP_TABLE_DELETE_ALL_KEY_TEMPLATE
            )
            await redis_service.delete_keys_by_pattern(
                CacheKeys.RealTime.REALTIME_TRIP_DELETE_ALL_KEY_TEMPLATE
            )

            console.print(f"\n[blue]Finished import in {round(finish - start, 2)} second(s)")

        @cli.command(
            name="seedrealtimefromfile",
            help="Loads GTFS-RT trip updates from a local JSON file into rt_trip / rt_stop_time",
        )
        @click.option(
            "--file",
            "json_path",
            required=True,
            type=click.Path(exists=True, dir_okay=False, readable=True, path_type=str),
            help="Path to GTFS-RT JSON (e.g. tests/gtfs_test_data/TFI/realtime_e2e_trip_updates.json)",
        )
        @click.option("-dataset", default="", help="Dataset label; default from app settings")
        @click.option(
            "--set-time-to-now",
            is_flag=True,
            help=(
                "Before import: move static GTFS stop_times for trips in this JSON to a window around "
                "the current clock (preserving spacing), repoint those trips to a calendar that runs on "
                "today's weekday (so weekend local testing works with weekday-only fixture services), "
                "and patch trip start_date/start_time in the payload. For local testing only; keep "
                "CI/pipeline on the committed JSON without this flag."
            ),
        )
        @make_sync
        @concurrency(1)
        async def seedrealtimefromfile(json_path: str, dataset: str, set_time_to_now: bool):
            """Populate realtime trip/stop-time tables from a file (for tests and local dev)."""

            console = Console()
            realtime_dataset = dataset or lib_settings.app.GTFS_TFI_DATASET
            payload = json.loads(Path(json_path).read_text(encoding="utf-8"))

            if set_time_to_now:
                async with async_session_factory() as session:
                    svc = await shift_db_stop_times_and_patch_payload_for_now(
                        session, realtime_dataset, payload
                    )
                msg = "[yellow]Adjusted static stop_times + JSON trip times to now (--set-time-to-now)."
                if svc:
                    msg += f" E2E trips use calendar service_id={svc} for today's weekday."
                console.print(msg)

            importer = RealTimeImporter(url="", api_key="", dataset=realtime_dataset)
            total_stop_times, total_trips = await importer.import_from_payload(payload)
            console.print(
                f"[green]Seeded realtime for dataset {realtime_dataset}: "
                f"{total_trips} rt_trip row(s) imported, {total_stop_times} rt_stop_time row(s) imported."
            )

            redis_service = await provide_redis_service()
            await redis_service.delete_keys_by_pattern(
                CacheKeys.RealTime.REALTIME_STOP_DELETE_ALL_KEY_TEMPLATE
            )
            await redis_service.delete_keys_by_pattern(
                CacheKeys.RealTime.REALTIME_STOP_TABLE_DELETE_ALL_KEY_TEMPLATE
            )
            await redis_service.delete_keys_by_pattern(
                CacheKeys.RealTime.REALTIME_TRIP_DELETE_ALL_KEY_TEMPLATE
            )

        @cli.command(
            name="importrealtimevehicles", help="Imports GTFS realtime vehicle data into the database"
        )
        @click.option("-url", help="Override the default URL for the GTFS realtime vehicle data")
        @click.option("-apikey", help="Override the default API key for the GTFS realtime vehicle data")
        @click.option("-dataset", help="Override the default dataset that the data will be saved against")
        @make_sync
        @skip_if_lock_held(
            _CLI_LOCK_GTFS_STATIC_IMPORT,
            skip_message="Skipped: GTFS static import is in progress",
        )
        @concurrency(1)
        async def importrealtimevehicles(url: str, apikey: str, dataset: str):
            """Imports GTFS realtime vehicle data into the database"""

            start: float = time.perf_counter()
            console = Console()
            console.print("Importing GTFS realtime data...")

            from SimplyTransport.lib import settings

            if url:
                realtime_url = url
                console.print(f"\nOverriding URL: {realtime_url}")
            else:
                realtime_url = settings.app.GTFS_TFI_REALTIME_VEHICLES_URL

            if apikey:
                realtime_apikey = apikey
                console.print(f"\nOverriding API key: {realtime_apikey}")
            else:
                realtime_apikey = settings.app.GTFS_TFI_API_KEY_2

            if dataset:
                realtime_dataset = dataset
                console.print(f"\nOverriding dataset: {realtime_dataset}")
            else:
                realtime_dataset = settings.app.GTFS_TFI_DATASET

            importer = RealTimeVehiclesImporter(
                url=realtime_url, api_key=realtime_apikey, dataset=realtime_dataset
            )

            console.print(f"\nImporting using dataset: {realtime_dataset} from {realtime_url}")

            data = await importer.get_data()

            if data is None:
                console.print(
                    "[red]Error: No data returned from API, either response was not 200 or JSON was invalid."
                )
                return

            console.print(f"\n{len(data['entity'])} entities returned from API")

            console.print("\nImporting Vehicles")
            total_vehicles = await importer.import_vehicles(data)

            finish: float = time.perf_counter()
            attributes = {
                "dataset": realtime_dataset,
                "total_vehicles": total_vehicles,
                "time_taken(s)": round(finish - start, 2),
            }
            await create_event_with_session(
                EventType.REALTIME_VEHICLES_DATABASE_UPDATED,
                "Realtime vehicles database updated with new realtime information",
                attributes,
            )

            redis_service = await provide_redis_service()
            await redis_service.delete_keys_by_pattern(CacheKeys.StopMaps.STOP_MAP_DELETE_ALL_KEY_TEMPLATE)
            await redis_service.delete_keys_by_pattern(CacheKeys.RouteMaps.ROUTE_MAP_DELETE_ALL_KEY_TEMPLATE)

            console.print(f"\n[blue]Finished import in {round(finish - start, 2)} second(s)")

        @cli.command(name="create_tables", help="Creates the database tables")
        @make_sync
        async def create_tables():
            """Creates the database tables"""

            console = Console()
            console.print("Creating database tables...")

            await db_services.create_database_tables()

        @cli.command(name="importstopfeatures", help="Imports stop features into the database")
        @click.option("-dir", help="Override the directory containing the stop feature data to import")
        @make_sync
        async def importstopfeatures(dir: str):
            """Imports stop features into the database"""

            start: float = time.perf_counter()
            console = Console()
            console.print("Importing stop features data...")

            dir = gtfs_directory_validator(dir, console)

            dataset = gtfs_dataset_label_from_import_dir(dir)
            response = click.prompt(
                f"\nYou are about to import this dataset and assign it to '{dataset}'. "
                "Press 'y' to continue, anything else to abort: ",
                type=str,
                default="",
                show_default=False,
            )
            if response != "y":
                console.print("[red]Aborting import...")
                return

            def geojson_cleaner(filename: str) -> geojson.FeatureCollection:
                console.print(f"Cleaning {filename}...")

                with open(filename, encoding="utf8") as f:
                    data = json.load(f)

                # Convert the coordinates to numbers from strings
                # This is needed because geojson doesn't support floats and for some TFI reason
                # thats what the data is formatted with
                for feature in data["features"]:
                    feature["geometry"]["coordinates"] = [
                        float(coord) for coord in feature["geometry"]["coordinates"]
                    ]

                json_string = json.dumps(data)

                # Some data has double quotes around booleans, this is invalid so we need to replace them
                json_string = json_string.replace('"False"', "false").replace('"True"', "true")

                return geojson.loads(json_string)

            console.print("\nReading files and cleaning data...")
            stops = geojson_cleaner(f"{dir}stops.geojson")
            poles = geojson_cleaner(f"{dir}poles.geojson")
            shelters = geojson_cleaner(f"{dir}shelters.geojson")
            rtpis = geojson_cleaner(f"{dir}rtpi.geojson")

            console.print("\nImporting stop features...")
            importer = StopFeaturesImporter(
                dataset=dataset, stops=stops, poles=poles, shelters=shelters, rtpis=rtpis
            )

            await importer.clear_database()

            stop_feature_attributes = await importer.import_stop_features()

            finish: float = time.perf_counter()

            attributes = {
                "stop_features": stop_feature_attributes,
                "dataset": dataset,
                "time_taken(s)": round(finish - start, 2),
            }

            await create_event_with_session(
                EventType.STOP_FEATURES_DATABASE_UPDATED,
                "Stop features database updated with latest stop features",
                attributes,
            )

            console.print(f"\n[blue]Finished import in {round(finish - start, 2)} second(s)")

        @cli.command(name="recreate_indexes", help="Recreates the indexes on a given table")
        @click.option("-table", help="The table to recreate the indexes on")
        @make_sync
        async def recreate_indexes(table: str | None = None):
            """Recreates the indexes on a given table"""

            console = Console()
            console.print("Recreating indexes...")
            if table is None:
                console.print("[yellow]No table specified to recreate indexes on from the -table argument")
                response = click.prompt(
                    "\nYou are about to recreate indexes on all tables. Press 'y' to continue, "
                    "anything else to abort: ",
                    type=str,
                    default="",
                    show_default=False,
                )
                if response != "y":
                    console.print("[red]Aborting recreate indexes...")
                    return
            else:
                console.print(f"Recreating indexes on table {table}")
                response = click.prompt(
                    f"\nYou are about to recreate indexes on table {table}. Press 'y' to continue, "
                    "anything else to abort: ",
                    type=str,
                    default="",
                    show_default=False,
                )
                if response != "y":
                    console.print("[red]Aborting recreate indexes...")
                    return

            start = time.perf_counter()

            await db_services.recreate_indexes(table)

            finish = time.perf_counter()
            console.print(f"\n[blue]Finished recreating indexes in {round(finish - start, 2)} second(s)")

        @cli.command(name="cleanupevents", help="Cleans up expired events from the database")
        @click.option("-event", help="Cleanup just a specific event type")
        @make_sync
        async def cleanupevents(event: str | None = None):
            """Cleans up expired events from the database"""

            start: float = time.perf_counter()
            console = Console()
            console.print("Cleaning up events...")

            if event:
                try:
                    event = EventType(event)
                except ValueError:
                    console.print(f"[red]Error: Event type '{event}' does not exist.")
                    return

            number_deleted = 0
            async with async_session_factory() as session:
                event_repo = await provide_event_repo(session)
                if event:
                    console.print(f"\nCleaning up just event type: {event}")
                    number_deleted = await event_repo.cleanup_events(event_type=event)
                else:
                    console.print("\nCleaning up all events")
                    number_deleted = await event_repo.cleanup_events()

            finish: float = time.perf_counter()

            attributes = {
                "number_deleted": number_deleted,
                "time_taken(s)": round(finish - start, 2),
            }
            await create_event_with_session(
                EventType.CLEANUP_EVENTS_DELETED,
                "Expired events cleaned up from the database",
                attributes,
            )
            console.print(f"\n[blue]Deleted {number_deleted} events")
            console.print(f"\n[blue]Finished cleanup in {round(finish - start, 2)} second(s)")

        @cli.command(name="flushredis", help="Flushes the Redis cache")
        @make_sync
        async def flushredis():
            """Flushes the Redis cache"""

            console = Console()
            console.print("Flushing the Redis cache...")

            redis_service = await provide_redis_service()

            total_keys = await redis_service.count_all_keys()
            console.print(f"\nTotal keys in the Redis cache: {total_keys}")

            await redis_service.delete_all_keys()
            console.print("\n[blue]Finished flushing the Redis cache")

        @cli.command(name="generatestatistics", help="Generates the statistics for the database")
        @make_sync
        async def generatestatistics():
            from SimplyTransport.lib.gtfs_dataset import generate_database_statistics

            console = Console()
            console.print("Generating statistics...")
            time_taken = await generate_database_statistics()
            console.print(f"\n[blue]Finished generating statistics in {time_taken} second(s)")

        @cli.command(
            name="recorddelays", help="Records the stop time delays for every schedule in the database"
        )
        @make_sync
        @skip_if_lock_held(
            _CLI_LOCK_GTFS_STATIC_IMPORT,
            skip_message="Skipped: GTFS static import is in progress",
        )
        @concurrency(1)
        async def recorddelays():
            console = Console()
            console.print("Recording delays...")
            start = time.perf_counter()

            async with async_timescale_session_factory() as timescale_session:
                async with async_session_factory() as session:
                    delays_service = await provide_delays_service(
                        timescale_db_session=timescale_session,
                        db_session=session,
                        redis_cache=await provide_redis_service(),
                    )
                    delays_recorded = await delays_service.record_all_delays()

            finish = time.perf_counter()

            attributes = {
                "total_delays": delays_recorded,
                "time_taken(s)": round(finish - start, 2),
            }
            await create_event_with_session(
                EventType.RECORD_TS_STOP_TIMES,
                "Delays recorded for every active schedule",
                attributes,
            )
            logger.info(f"Finished recording delays in {round(finish - start, 2)} second(s)")
            console.print(f"\n[blue]Finished recording delays in {round(finish - start, 2)} second(s)")

        @cli.command(name="cleanupdelays", help="Cleans up the old delays from the database")
        @make_sync
        async def cleanupdelays():
            console = Console()
            console.print("Cleaning up delays...")
            start = time.perf_counter()

            async with async_timescale_session_factory() as timescale_session:
                async with async_session_factory() as session:
                    delays_service = await provide_delays_service(
                        timescale_db_session=timescale_session,
                        db_session=session,
                        redis_cache=await provide_redis_service(),
                    )
                    number_deleted = await delays_service.cleanup_old_delays()

            finish = time.perf_counter()

            attributes = {
                "time_taken(s)": round(finish - start, 2),
                "number_deleted": number_deleted,
            }
            await create_event_with_session(
                EventType.CLEANUP_DELAYS_DELETED,
                "Old delays cleaned up from the database",
                attributes,
            )
            logger.info(f"Finished cleaning up delays in {round(finish - start, 2)} second(s)")
            console.print(f"\n[blue]Finished cleaning up delays in {round(finish - start, 2)} second(s)")
