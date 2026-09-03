from __future__ import annotations

import asyncio
import json
import os
import subprocess
from collections.abc import AsyncIterator
from datetime import datetime, time, timedelta
from pathlib import Path

import pytest
import pytest_asyncio
from litestar import Litestar
from litestar.testing import AsyncTestClient

COMPOSE_PROJECT = "simplytransport-test"
REPO_ROOT = Path(__file__).resolve().parents[2]
COMPOSE_FILE = REPO_ROOT / "docker-compose.test.yaml"
GTFS_FIXTURE_DIR = REPO_ROOT / "tests" / "gtfs_test_data" / "TFI"

TEST_ENV = {
    "DB_URL": "postgresql+asyncpg://st_test:st_test@127.0.0.1:15432/st_database",
    "TIMESCALE_URL": "postgresql+asyncpg://st_test:st_test@127.0.0.1:15433/st_ts_database",
    "REDIS_HOST": "127.0.0.1",
    "REDIS_PORT": "16379",
    "REDIS_PASSWORD": "",
    "ENVIRONMENT": "TEST",
    "GTFS_TFI_DATASET": "TFI",
}


def _compose(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["docker", "compose", "-p", COMPOSE_PROJECT, "-f", str(COMPOSE_FILE), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def _require_docker() -> None:
    try:
        result = subprocess.run(["docker", "info"], capture_output=True, text=True, check=False)
    except FileNotFoundError as exc:
        raise RuntimeError(
            "Docker is required for integration tests. Install Docker Desktop and retry."
        ) from exc
    if result.returncode != 0:
        raise RuntimeError(
            "Docker is required for integration tests. Start Docker Desktop and retry.\n"
            f"{result.stderr.strip()}"
        )


def _apply_test_env() -> None:
    os.environ.update(TEST_ENV)
    from SimplyTransport.lib.db.database import reset_engines
    from SimplyTransport.lib.db.timescale_database import reset_timescale_engines
    from SimplyTransport.lib.settings import reset_settings

    reset_settings()
    reset_engines()
    reset_timescale_engines()


async def _wait_for_sql(url: str, *, attempts: int = 40, delay_s: float = 0.5) -> None:
    """pg_isready can pass before Timescale finishes restarting after init."""
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    last_error: Exception | None = None
    engine = create_async_engine(url, pool_pre_ping=True)
    try:
        for _ in range(attempts):
            try:
                async with engine.connect() as conn:
                    await conn.execute(text("SELECT 1"))
                return
            except Exception as exc:
                last_error = exc
                await asyncio.sleep(delay_s)
    finally:
        await engine.dispose()
    raise RuntimeError(f"Timed out waiting for a SQL connection to {url}") from last_error


def _wait_for_stack() -> None:
    from SimplyTransport.lib import settings

    async def _wait_both() -> None:
        await _wait_for_sql(settings.app.DB_URL)
        await _wait_for_sql(settings.app.TIMESCALE_URL)

    asyncio.run(_wait_both())


async def _seed_delay_rows() -> None:
    from SimplyTransport.lib.db.timescale_database import async_timescale_session_factory
    from SimplyTransport.timescale.ts_stop_times.model import TS_StopTimeModel

    now = datetime.now()
    async with async_timescale_session_factory() as session:
        session.add_all(
            [
                TS_StopTimeModel(
                    Timestamp=now - timedelta(days=1),
                    stop_id="8240DB000324",
                    route_code="4",
                    scheduled_time=time(8, 0, 0),
                    delay_in_seconds=120,
                ),
                TS_StopTimeModel(
                    Timestamp=now - timedelta(days=2),
                    stop_id="8240DB000324",
                    route_code="4",
                    scheduled_time=time(8, 0, 0),
                    delay_in_seconds=60,
                ),
                TS_StopTimeModel(
                    Timestamp=now - timedelta(days=3),
                    stop_id="8240DB000324",
                    route_code="4",
                    scheduled_time=time(8, 0, 0),
                    delay_in_seconds=180,
                ),
            ]
        )
        await session.commit()


def _seed_database() -> None:
    from SimplyTransport.lib.db.database import get_async_engine, reset_engines
    from SimplyTransport.lib.db.services import create_database_tables
    from SimplyTransport.lib.db.timescale_database import reset_timescale_engines
    from SimplyTransport.lib.gtfs_dataset import generate_database_statistics, import_gtfs_dataset

    gtfs_dir = str(GTFS_FIXTURE_DIR).replace("\\", "/") + "/"

    async def _seed() -> None:
        import SimplyTransport.timescale  # noqa: F401
        from SimplyTransport.lib.gtfs_realtime_importers import RealTimeImporter

        await create_database_tables()
        await import_gtfs_dataset(gtfs_dir)
        await generate_database_statistics()
        payload = json.loads(
            (GTFS_FIXTURE_DIR / "realtime_e2e_trip_updates.json").read_text(encoding="utf-8")
        )
        await RealTimeImporter(url="", api_key="", dataset="TFI").import_from_payload(payload)
        await _seed_delay_rows()
        await get_async_engine().dispose()

    asyncio.run(_seed())
    # Drop cached engines so the test client does not reuse connections from the closed loop.
    reset_engines()
    reset_timescale_engines()


_stack_started = False


def _start_stack() -> None:
    global _stack_started
    if _stack_started:
        return
    _require_docker()
    up = _compose("up", "-d", "--wait")
    if up.returncode != 0:
        _compose("down", "-v")
        raise RuntimeError(f"Failed to start the integration test Docker stack.\n{up.stdout}\n{up.stderr}")
    _stack_started = True
    _apply_test_env()
    try:
        _wait_for_stack()
        _seed_database()
    except Exception:
        logs = _compose("logs", "--no-color")
        print(f"Test stack logs:\n{logs.stdout}\n{logs.stderr}")
        _compose("down", "-v")
        _stack_started = False
        raise


def _stop_stack() -> None:
    global _stack_started
    if not _stack_started:
        return
    down = _compose("down", "-v")
    _stack_started = False
    if down.returncode != 0:
        print(f"Failed to tear down the test stack:\n{down.stdout}\n{down.stderr}")


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    # Tear down after the whole pytest process, not when pytest-asyncio
    # finalizes the session fixture (that can happen before tests run).
    _stop_stack()


@pytest.fixture(scope="session")
def test_stack() -> None:
    _start_stack()


@pytest.fixture(scope="session")
def app(test_stack: None) -> Litestar:
    """Always use this `app` fixture and never do `from app.main import app`
    inside a test module. We need to delay import of the `app.main` module
    until as late as possible to ensure we can mock everything necessary before
    the application instance is constructed.

    Returns:
        The application instance.
    """
    from SimplyTransport.app import create_app

    return create_app()


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def async_client(app: Litestar) -> AsyncIterator[AsyncTestClient]:
    async with AsyncTestClient(app=app) as client:
        yield client
