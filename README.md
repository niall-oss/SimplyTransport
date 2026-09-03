[![CI/CD](https://github.com/ANIALLATOR114/SimplyTransport/actions/workflows/tests_on_merge_main.yaml/badge.svg?branch=main)](https://github.com/ANIALLATOR114/SimplyTransport/actions/workflows/tests_on_merge_main.yaml)
[![Better Stack Badge](https://uptime.betterstack.com/status-badges/v1/monitor/10yqf.svg)](https://uptime.betterstack.com/?utm_source=status_badge)

# 🚌 SimplyTransport

- Litestar Python ASGI web app
- API & Website for real-time transport updates and schedules
- GTFS and GTFS-R data ingestor

## 📖 Content

- [About](#about)
- [API Docs](#api-documentation)
- [Web Interface](#web-interface)
  - [Maps](#maps)
- [CLI Interface](#cli-interface)
- [Contributing](CONTRIBUTING.md)

- [Installation](#installation)

  - [Running Locally](#running-locally)
  - [Running in Production](#running-in-production)

- [Docker Deployment](#docker-deployment)

  - [Project Structure](#project-structure)
  - [Development Environment](#development-environment)
  - [Production Environment](#production-environment)
  - [Container Health Checks](#container-health-checks)
  - [Environment Variables](#environment-variables)
  - [Networks](#networks)
  - [Volumes](#volumes)

- [Development](#development)
  - [Project Structure](#project-structure)
    - [Controllers](#controllers)
    - [Domain](#domain)
    - [Services](#services)
    - [Lib](#lib)
    - [Templates](#templates)
  - [Database](#database)
    - [Migrations](#migrations)
- [Telemetry and Logs](#telemetry-and-logs)

  - [Telemetry](#telemetry)
  - [Logging](#logging)
    - [Regular Logging](#regular-logging)
    - [Exception Logging](#exception-logging)

- [Testing](#testing)
  - [Integration Tests](#integration-tests)
  - [Unit Tests](#unit-tests)
  - [Code Coverage](#code-coverage)

## About

> [!NOTE]
> The accuracy of the data is entirely the responsability of the transport providers

[GTFS Reference](https://gtfs.org/schedule/) The standard format for the transport data

[TFI Public GTFS Datasets](https://www.transportforireland.ie/transitData/PT_Data.html) The Irish governments GTFS data

[GTFS-R](https://developer.nationaltransport.ie/apis) The Irish governments Realtime data feeds. You cannot query this as you might expect, you must download the entire feed (rate limited to 1/min)

SimplyTransport is designed to continually request the GTFS-R feed as often as possible.
The static schedules are updated randomly by the data provider. SimplyTransport checks nightly to see if it needs to perform an update.
Realtime data is updated every minute.

## API Documentation

[Website Link](https://simplytransport.ie/apidocs)

[Redoc](https://simplytransport.ie/docs/redoc)

[Swagger](https://simplytransport.ie/docs/swagger)

[StopLight](https://simplytransport.ie/docs/elements#/)

[OpenAPI Json](https://simplytransport.ie/docs/openapi.json)

[OpenAPI Yaml](https://simplytransport.ie/docs/openapi.yaml)

- [x] Agencies
- [x] Stops
- [x] Routes
- [x] Calendar
- [x] CalendarDates
- [x] StopTimes
- [x] Trips
- [x] Shapes
- [x] Schedules
- [x] Realtime
- [x] Realtime Vehicles
- [x] StopFeatures

## Web Interface

- [x] Homepage
- [x] About
- [x] Stop
  - [x] Realtime
  - [x] Schedule
  - [x] Stop Features
- [x] Route
- [x] Trip
- [x] Search Page
  - [x] Stops
  - [x] Routes
- [x] Maps

### Maps

Maps use **MapLibre GL JS** in the browser. The server exposes JSON under `/api/v1/map/...` (route polylines, stops, vehicles, etc.); the client fetches that data and draws layers on an OpenStreetMap raster basemap.

- [x] Maps on route pages
- [x] Maps on stop pages
- [x] Aggregation of stops
- [x] Aggregation of routes

## CLI Interface

> [!NOTE]
> All commands are prefixed with `litestar`

This extends the standard litestar cli. You can view all the commands by just running `litestar`.

- [x] Application Settings `settings`
- [x] Documentation Links `docs`
- [x] GTFS Importer `importgtfs`
- [x] Realtime Updater `importrealtime`
- [x] Stop Feature Importer `importstopfeatures`
- [x] Create Database tables manually `create_tables`
- [x] Recreate all database indexes `recreate_indexes`
- [x] Cleanup expired events from the database `cleanupevents`
- [x] Flush the redis cache `flushcache`

# Installation

> [!NOTE]
> Requires **Python 3.14.3** (not a pre-release alpha/beta). [uv](https://github.com/astral-sh/uv) is used in CI and is recommended locally: `uv python install 3.14.3` then `uv venv --python 3.14.3` (or `uv venv`—see [`.python-version`](.python-version)).
> On **Ubuntu/Linux** servers, install build tools before `pip`/`uv pip install` if native-extension wheels are missing—see [deployment_linux/README.md](deployment_linux/README.md).

First clone down the project in your desired directory

```
git clone https://github.com/ANIALLATOR114/SimplyTransport.git
```

Create a virtual environment in the project root and install dependencies (example with uv):

```
uv python install 3.14.3
uv venv --python 3.14.3
```

Activate the virtual environment (paths differ by OS):

```
# Linux / macOS
source .venv/bin/activate

# Windows (PowerShell)
.venv\Scripts\Activate.ps1

# Windows (Git Bash)
source .venv/Scripts/activate
```

```
uv pip install -r requirements-top-level.txt
uv pip install -r requirements-dev.txt
```

Alternatively, using the standard library only (the `python` you use must satisfy **3.14.3** or newer in the 3.14 line per `pyproject.toml`; check with `python --version`):

```
python3.14 -m venv .venv
pip install -r requirements-top-level.txt
pip install -r requirements-dev.txt
```

Create a copy of .env.example and populate it with your environment variables

```
cp .env.example .env
```

Open the `.env` file and change the example variables for the following fields. You can set these to whatever you like as they will be unique to your local deployment.

Notice how the `POSTGRES_` variables and the `TIMESCALE_` map into the URL you're going to try and connect to. Docker-compose will create 2 DBs using these variables for you.

```
# Database
DB_URL=postgresql+asyncpg://example2:example3@localhost:5432/example1
DB_ECHO=false
TIMESCALE_URL=postgresql+asyncpg://example:example@localhost:5433/example

# Postgres Docker
POSTGRES_DB=example1
POSTGRES_USER=example2
POSTGRES_PASSWORD=example3

# Timescale Docker
TIMESCALE_DB=example
TIMESCALE_USER=example
TIMESCALE_PASSWORD=example

# Redis
REDIS_PASSWORD=example
```

Once you have the variables above set please run the command in [Database](#database)

## Docker Deployment

The application is containerized using Docker and can be run in both development and production environments.

### Project Structure

```
.
├── Docker/
│   ├── app/
│   │   ├── Dockerfile
│   │   └── docker-compose.yaml
│   ├── postgres/
│   │   └── docker-compose.yaml
│   ├── redis/
│   │   └── docker-compose.yaml
│   ├── timescale/
│   │   └── docker-compose.yaml
│   └── otel-collector/
│       └── docker-compose.yaml
├── docker-compose.dev.yaml
├── docker-compose.test.yaml
└── docker-compose.prod.yaml
```

### Development Environment

For local development, you can run just the dependencies (databases, Redis, and OpenTelemetry):

```bash
docker-compose -f docker-compose.dev.yaml up -d
```

This will start:

- PostgreSQL (port 5432)
- Redis (port 6379)
- TimescaleDB (port 5433)
- OpenTelemetry Collector (port 4318)

You can then run the application locally using:

```bash
litestar run
```

### Production Environment

For production deployment, use:

```bash
docker-compose -f docker-compose.prod.yaml up -d
```

This will start all services including the application:

- SimplyTransport App (port 8000)
- PostgreSQL (port 5432)
- Redis (port 6379)
- TimescaleDB (port 5433)
- OpenTelemetry Collector (port 4318)

### Container Health Checks

The application container includes health checks that monitor its status:

- Endpoint: `/healthcheck`
- Interval: 30s
- Timeout: 2s
- Retries: 10
- Start period: 40s

### Environment Variables

Make sure to set up your environment variables in a `.env` file. See `.env.example` for required variables.

### Networks

All services are connected through a Docker network named `simplytransport-network`.

### Volumes

The application mounts the following volumes:

- `static/`: For serving static files
- `deployment_linux/collector-config.yaml`: OpenTelemetry collector configuration

## Running Locally

Note - Docker is available - see above for more details

You can run the app using the litestar run command for local development which will use a uvicorn worker to launch the app on 127.0.0.1:8000

When you run `litestar <command>` it will try and find the Litestar app to launch via the `.env` file. You shouldnt need to have changed this from the `.env.example`

```
litestar run
```

This will reload the app when changes are made for development convenience

```
litestar run --reload
```

The custom commands I've added to the app can be run using the litestar command in the same way

```
litestar settings
litestar docs
litestar importgtfs
litestar importrealtime
litestar importstopfeatures
litestar seedrealtimefromfile
litestar generatestatistics
litestar recorddelays
```

### Local testing

To exercise the realtime UI against the small **TFI** fixture under `tests/gtfs_test_data` (for example `/realtime/stop/RT_E2E_S1`), import that GTFS directory first, then seed GTFS-RT from the E2E JSON. Use **`--set-time-to-now`** so static `stop_time` rows and trip calendars line up with your machine clock and today’s weekday (the committed fixture times are fixed; without this flag the stop page’s time window often shows nothing).

```
litestar importgtfs -dir ./tests/gtfs_test_data/TFI/
litestar seedrealtimefromfile --file ./tests/gtfs_test_data/TFI/realtime_e2e_trip_updates.json --set-time-to-now
```

`importgtfs` stores the **dataset** tag as the **GTFS folder name** (the last segment of `-dir`, e.g. **`TFI`** for `.../TFI/`). `seedrealtimefromfile` must use the **same** tag: it defaults to **`GTFS_TFI_DATASET`** in `.env` (set that to `TFI` for this layout), or pass **`-dataset TFI`** explicitly. Omit **`--set-time-to-now`** in CI or any pipeline that must stay deterministic.

## Running in Production

Note - Docker is available - see above for more details

You should use uvicorn directly to run the app in production and not litestar, this will allow you to configure the number of workers, ports etc

```
uvicorn SimplyTransport.app:create_app --port 8000 --env-file .env
```

Example configs are available for Supervisor and Nginx for hosting on Linux.
This allows you to run the app as a service and proxy requests to it from Nginx, Supervisor will manage the processess and restart them if they fail.
Once configured you can start the app under supervisor using the following command

```
supervisorctl start simplytransport
```

It is advisable to have nginx serve the static files for the app, you can do this by adding the following to your nginx config.
A similar line is already present in the example config as well as a robots.txt example

```
location /static {
    alias /path/to/SimplyTransport/static;
}
```

# Development

## Project Structure

This app is a Litestar Python ASGI web application, it's organised into controllers, domain, services, lib extensions and templates.

### Controllers

This is where the endpoints for the app are defined, these are the entry points for the API and the web interface.

Each controller will be injected with any services or repositories it requires to function.
Controllers should be kept as thin as possible, they should only be responsible for handling the request and returning a response.

The routing for each controller is configured in the `__init__.py` file in the controllers directory.
This file also controls the prefix for the routes, if schema generation is enabled and any auth requirements.

### Domain

This is where the models for the app are defined, these are the objects that are returned by the API and used in endpoints.

Most of these will be based closely on the GTFS data but some are custom objects which could be a transformation of the gtfs models.

Commonly these will have a SQLAlchemy model associated with them (should it require one).
Each model should have its own dedicated repository which is used to query the database for that object.

### Services

This is where more complicated logic is organised.

Services should be injected with any repositories they require to function.

Services will combine data from multiple repositories to create a more complex object or perform some logic.

### Lib

This is where any extensions to the app are defined.

This includes things like the database, the schema generator, logging, etc.

### Templates

This is where the templates for the web interface are defined.

These are jinja2 templates which are rendered by the controllers.

There is a base template which is extended by any other templates that define a distinct web page.

Partial templates are smaller templates that are returned with the intention to inject them into the calling template. HTMX is used to request and swap these partials in and out of the DOM.

## Database

This application expects 2 Postgres databases to be available at the urls specified in the .env file.

There is a `docker-compose.yaml` available in the root directory of the project which will create the postgres databases for you as well as a redis instance for caching.

```
docker-compose up -d
```

### Migrations

This application uses Alembic for migrations, you can create a new migration using the following command
You should be in the root directory.
Since there are 2 databases you will need to specify which one you want to operate on.
When generating migrations you need to scope the migration to the correct database using the `-x` flag and the `db` variable as well as the --name.

```
alembic -x db=main --name main revision --autogenerate -m "The name of my migration"
```

```
alembic -x db=timescale --name timescale revision --autogenerate -m "The name of my migration"
```

To apply the migration to your database use the following command

```
alembic -x db=main --name main upgrade head
```

```
alembic -x db=timescale --name timescale upgrade head
```

# Telemetry and Logs

## Telemetry

SimplyTransport sends **traces, metrics, and logs** over OTLP/HTTP to an **OpenTelemetry Collector**, which forwards everything to the **.NET Aspire Dashboard**.

- **Dev:** `docker compose -f docker-compose.dev.yaml up -d` starts Postgres, Redis, Timescale, the collector, and Aspire. Open the dashboard at **http://localhost:18888**.
- **Prod:** `docker-compose.prod.yaml` includes the same Aspire and collector services. Publish port **18888** on the server to view the dashboard from your LAN (treat it like any internal admin tool: use firewall or VPN as appropriate). Prefer **not** exposing OTLP ports **4317**/**4318** beyond the Docker network.

Set **`OTEL_EXPORTER_OTLP_ENDPOINT`** on the app (default `http://127.0.0.1:4318` when the process runs on the host). The app container defaults to **`http://opentelemetry-collector:4318`**. The collector forwards to Aspire using **`ASPIRE_OTLP_ENDPOINT`** (default `aspire-dashboard:18889` for OTLP/gRPC on Aspire 9.x inside Docker).

Telemetry export runs only when **`ENVIRONMENT`** is **DEV** or **PROD** (CI test envs do not export).

Instrumentation includes:

- [x] Litestar / ASGI (HTTP requests)
- [x] Database queries (SQLAlchemy)
- [x] Redis (client spans)

## Logging

SimplyTransport uses **structlog** with rich for readable console output. In **DEV** and **PROD**, logs are also sent to the collector via **OpenTelemetry Logs** (same OTLP base URL as traces), so they show in Aspire next to traces. The console handler remains the best place for verbose exceptions and local variable context.

# Testing

SimplyTransport has **Integration** and **Unit** tests implemented using pytest.

`pytest` is enough. Integration tests start their own Docker Compose stack (Postgres, TimescaleDB, Redis), load the GTFS fixture data from `tests/gtfs_test_data/TFI/`, then tear the stack down. Docker Desktop must be running. Unit tests do not need Docker:

```
pytest
pytest tests/unit
pytest tests/integration
```

If a run is killed mid-suite, leftover containers can be removed with:

```
docker compose -p simplytransport-test -f docker-compose.test.yaml down -v
```

or

```
python -m pytest
```

## Integration Tests

The integration tests use a test client to make requests to a test version of SimplyTransport.

Here is an example in `test_root.py`

```python
from litestar.testing import TestClient


def test_root_200(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "Welcome to SimplyTransport" in response.text
```

## Unit Tests

The unit tests make heavy use of mocking to test the logic of the app in isolation as dependency injection is used throughout the core services.

Here is an example in `test_schedule_service.py`

```python
from unittest.mock import AsyncMock,
from SimplyTransport.domain.services.schedule_service import ScheduleService
from SimplyTransport.domain.enums import DayOfWeek

@pytest.mark.asyncio
async def test_get_schedule_on_stop_for_day_should_call_repository():
    # Arrange
    schedule_repository = AsyncMock()
    calendar_date_repository = AsyncMock()
    schedule_service = ScheduleService(
        schedule_repository=schedule_repository,
        calendar_date_repository=calendar_date_repository,
    )

    stop_id = "stop_id"
    day = DayOfWeek.MONDAY

    # Act
    await schedule_service.get_schedule_on_stop_for_day(stop_id=stop_id, day=day)

    # Assert
    schedule_repository.get_schedule_on_stop_for_day.assert_called_once_with(
        stop_id=stop_id, day=day
    )
```

In this example we specifically want to ensure that the `get_schedule_on_stop_for_day` method on the `schedule_repository` is called with the correct arguments and just one time.

## Code Coverage

Code coverage is measured using coverage, you can run the tests with coverage using the following command in the root directory.

```
coverage run -m pytest
```

You can then generate a report on your cmd using the following command

```
coverage report
```

You can also generate a html report using the following command

```
coverage html --show-contexts
```

This will generate a htmlcov directory in the root directory where you can open index.html to view the report in your browser.

## Code Quality Tools

### Pre-commit Hooks

The hooks are configured to run Ruff with the same settings as the CI pipeline.

### Installation

Install development dependencies:

```bash
pip install -r requirements-dev.txt
pre-commit install
```

### Usage

The hooks will run automatically on every commit. Ruff will:

1. Check for code quality issues
2. Format your code (similar to Black)
3. Auto-fix common issues
4. Include the changes in your commit

You can also run Ruff manually:

```bash
# Check code
ruff check .

# Format code
ruff format .

# Fix issues automatically
ruff check --fix .
```

### Current Hooks

- **ruff**: Fast Python linter and formatter (written in Rust)
  - Line length: 110 characters
  - Targets: SimplyTransport/ and tests/ directories
  - Enabled rules:
    - pycodestyle errors (E)
    - pyflakes (F)
    - isort (I)
    - flake8-bugbear (B)
    - flake8-comprehensions (C4)
    - pyupgrade (UP)
    - pep8-naming (N)
    - pycodestyle warnings (W)

### Configuration Files

- `.pre-commit-config.yaml`: Pre-commit hook configuration
- `pyproject.toml`: Ruff configuration
- `requirements-dev.txt`: Development dependencies

### Pyright - Type checking

Pyright is a static type checker for Python. It is not yet enforced in the CI pipeline as the project is not yet fully typed.

It is currently set to basic but the goal is to get it to strict.

You can run Pyright manually using the following command:

```bash
pyright
```

This will check the entire project for type errors and warnings.
