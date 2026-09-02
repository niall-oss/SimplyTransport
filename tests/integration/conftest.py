from __future__ import annotations

import asyncio
import os
import subprocess
from collections import abc
from pathlib import Path

import pytest
from litestar import Litestar
from litestar.testing import AsyncTestClient, TestClient

COMPOSE_PROJECT = "simplytransport-test"
REPO_ROOT = Path(__file__).resolve().parents[2]
COMPOSE_FILE = REPO_ROOT / "docker-compose.test.yaml"
GTFS_FIXTURE_DIR = REPO_ROOT / "tests" / "gtfs_test_data" / "TFI"

TEST_ENV = {
    "DB_URL": "postgresql+asyncpg://st_test:st_test@localhost:15432/st_database",
    "DB_URL_SYNC": "postgresql+psycopg2://st_test:st_test@localhost:15432/st_database",
    "TIMESCALE_URL": "postgresql+asyncpg://st_test:st_test@localhost:15433/st_ts_database",
    "REDIS_HOST": "127.0.0.1",
    "REDIS_PORT": "16379",
    "REDIS_PASSWORD": "",
    "ENVIRONMENT": "TEST",
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


def _seed_database() -> None:
    from SimplyTransport.lib.db.services import create_database_sync
    from SimplyTransport.lib.gtfs_dataset import generate_database_statistics, import_gtfs_dataset

    create_database_sync()
    gtfs_dir = str(GTFS_FIXTURE_DIR).replace("\\", "/") + "/"
    asyncio.run(import_gtfs_dataset(gtfs_dir))
    asyncio.run(generate_database_statistics())


@pytest.fixture(scope="session")
def test_stack() -> abc.Iterator[None]:
    _require_docker()
    up = _compose("up", "-d", "--wait")
    if up.returncode != 0:
        _compose("down", "-v")
        raise RuntimeError(f"Failed to start the integration test Docker stack.\n{up.stdout}\n{up.stderr}")
    try:
        _apply_test_env()
        _seed_database()
        yield
    finally:
        down = _compose("down", "-v")
        if down.returncode != 0:
            print(f"Failed to tear down the test stack:\n{down.stdout}\n{down.stderr}")


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


@pytest.fixture(scope="session")
def async_client(app: Litestar) -> AsyncTestClient:
    return AsyncTestClient(app=app)


@pytest.fixture(scope="session")
def client(app: Litestar) -> abc.Iterator[TestClient]:
    """Client instance attached to app.

    Args:
        app: The app for testing.

    Returns:
        Test client instance.
    """
    with TestClient(app=app) as c:
        yield c
