import json
from collections.abc import AsyncIterator
from contextlib import ExitStack
from datetime import date, datetime, time
from pathlib import Path
from unittest.mock import patch

import pytest
import pytest_asyncio
from SimplyTransport.domain.realtime.stop_time.rt_stop_time_model import RTStopTimeModel
from SimplyTransport.domain.realtime.trip.rt_trip_model import RTTripModel
from SimplyTransport.domain.realtime.vehicle.rt_vehicle_model import RTVehicleModel
from SimplyTransport.lib import gtfs_realtime_importers as rt
from SimplyTransport.lib import settings
from SimplyTransport.lib.gtfs_realtime_importers import RealTimeImporter, RealTimeVehiclesImporter
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

pytestmark = pytest.mark.asyncio(loop_scope="session")

E2E_JSON = Path(__file__).resolve().parents[1] / "gtfs_test_data" / "TFI" / "realtime_e2e_trip_updates.json"
OTHER = "OTHER"

type SessionMaker = async_sessionmaker[AsyncSession]


async def _count(sessions: SessionMaker, model: type, dataset: str) -> int:
    async with sessions() as session:
        result = await session.scalar(select(func.count()).select_from(model).where(model.dataset == dataset))
        return int(result or 0)


async def _restore_tfi_realtime() -> None:
    payload = json.loads(E2E_JSON.read_text(encoding="utf-8"))
    await RealTimeImporter(url="", api_key="", dataset="TFI").import_from_payload(payload)


async def _clear_other_dataset(sessions: SessionMaker) -> None:
    async with sessions() as session:
        await session.execute(delete(RTTripModel).where(RTTripModel.dataset == OTHER))
        await session.execute(delete(RTStopTimeModel).where(RTStopTimeModel.dataset == OTHER))
        await session.execute(delete(RTVehicleModel).where(RTVehicleModel.dataset == OTHER))
        await session.commit()


async def _insert_other_dataset_rows(sessions: SessionMaker) -> None:
    await _clear_other_dataset(sessions)
    async with sessions() as session:
        session.add(
            RTTripModel(
                trip_id="OTHER_TRIP",
                route_id="OTHER_ROUTE",
                start_time=time(8, 0),
                start_date=date(2025, 3, 21),
                schedule_relationship="SCHEDULED",
                direction=0,
                entity_id="other-trip",
                dataset=OTHER,
            )
        )
        session.add(
            RTStopTimeModel(
                stop_id="OTHER_STOP",
                trip_id="OTHER_TRIP",
                stop_sequence=1,
                schedule_relationship="SCHEDULED",
                arrival_delay=0,
                departure_delay=0,
                entity_id="other-stop",
                dataset=OTHER,
            )
        )
        session.add(
            RTVehicleModel(
                vehicle_id=1,
                trip_id="OTHER_TRIP",
                time_of_update=datetime(2025, 3, 21, 8, 0),
                lat=53.3,
                lon=-6.2,
                dataset=OTHER,
            )
        )
        await session.commit()


@pytest_asyncio.fixture(autouse=True, scope="module", loop_scope="session")
async def rt_session_maker(test_stack: None) -> AsyncIterator[SessionMaker]:
    """Own engine so importer SQL does not share the TestClient's asyncpg loop."""
    engine: AsyncEngine = create_async_engine(settings.app.DB_URL, pool_pre_ping=True)
    sessions: SessionMaker = async_sessionmaker(engine, expire_on_commit=False)
    with ExitStack() as stack:
        stack.enter_context(patch.object(rt, "get_async_engine", return_value=engine))
        stack.enter_context(patch.object(rt, "async_session_factory", sessions))
        try:
            yield sessions
            await _restore_tfi_realtime()
            await _clear_other_dataset(sessions)
        finally:
            await engine.dispose()


async def test_import_from_payload_replaces_tfi_snapshot(rt_session_maker: SessionMaker) -> None:
    payload = json.loads(E2E_JSON.read_text(encoding="utf-8"))
    stop_count, trip_count = await RealTimeImporter("", "", "TFI").import_from_payload(payload)
    db_trips = await _count(rt_session_maker, RTTripModel, "TFI")
    db_stops = await _count(rt_session_maker, RTStopTimeModel, "TFI")
    assert (trip_count, stop_count, db_trips, db_stops) == (3, 2, 3, 2)


async def test_second_import_replaces_without_duplicate_rows(rt_session_maker: SessionMaker) -> None:
    payload = json.loads(E2E_JSON.read_text(encoding="utf-8"))
    importer = RealTimeImporter("", "", "TFI")
    await importer.import_from_payload(payload)
    await importer.import_from_payload(payload)
    assert await _count(rt_session_maker, RTTripModel, "TFI") == 3
    assert await _count(rt_session_maker, RTStopTimeModel, "TFI") == 2


async def test_import_skips_unknown_trip_and_stop_ids(rt_session_maker: SessionMaker) -> None:
    payload = {
        "entity": [
            {
                "id": "unknown-trip",
                "trip_update": {
                    "trip": {"trip_id": "NOT_IN_STATIC", "route_id": "3623_54684"},
                    "stop_time_update": [{"stop_id": "RT_E2E_S1", "stop_sequence": 1}],
                },
            },
            {
                "id": "unknown-stop",
                "trip_update": {
                    "trip": {
                        "trip_id": "RT_E2E_SCHED",
                        "route_id": "3623_54684",
                        "start_time": "12:00:00",
                        "start_date": "20250321",
                    },
                    "stop_time_update": [
                        {"stop_id": "NOPE", "stop_sequence": 1},
                        {"stop_id": "RT_E2E_S1", "stop_sequence": 1, "arrival": {"delay": 7}},
                    ],
                },
            },
        ]
    }
    stop_count, trip_count = await RealTimeImporter("", "", "TFI").import_from_payload(payload)
    assert trip_count == 1
    assert stop_count == 1
    async with rt_session_maker() as session:
        trip = await session.scalar(select(RTTripModel).where(RTTripModel.dataset == "TFI"))
        stop = await session.scalar(select(RTStopTimeModel).where(RTStopTimeModel.dataset == "TFI"))
    assert trip is not None
    assert trip.trip_id == "RT_E2E_SCHED"
    assert stop is not None
    assert stop.stop_id == "RT_E2E_S1"
    assert stop.arrival_delay == 7


async def test_import_does_not_delete_other_dataset_rows(rt_session_maker: SessionMaker) -> None:
    await _insert_other_dataset_rows(rt_session_maker)
    payload = json.loads(E2E_JSON.read_text(encoding="utf-8"))
    await RealTimeImporter("", "", "TFI").import_from_payload(payload)
    assert await _count(rt_session_maker, RTTripModel, OTHER) == 1
    assert await _count(rt_session_maker, RTStopTimeModel, OTHER) == 1
    assert await _count(rt_session_maker, RTVehicleModel, OTHER) == 1
    assert await _count(rt_session_maker, RTTripModel, "TFI") == 3


async def test_empty_feed_deletes_dataset_and_leaves_others(rt_session_maker: SessionMaker) -> None:
    await _insert_other_dataset_rows(rt_session_maker)
    stop_count, trip_count = await RealTimeImporter("", "", "TFI").import_from_payload({"entity": []})
    assert stop_count == 0
    assert trip_count == 0
    assert await _count(rt_session_maker, RTTripModel, "TFI") == 0
    assert await _count(rt_session_maker, RTStopTimeModel, "TFI") == 0
    assert await _count(rt_session_maker, RTTripModel, OTHER) == 1
    assert await _count(rt_session_maker, RTStopTimeModel, OTHER) == 1


async def test_import_vehicles_keeps_only_static_trips(rt_session_maker: SessionMaker) -> None:
    payload = {
        "entity": [
            {
                "id": "ok",
                "vehicle": {
                    "trip": {"trip_id": "RT_E2E_SCHED"},
                    "vehicle": {"id": "42"},
                    "timestamp": "1705880460",
                    "position": {"latitude": 53.35, "longitude": -6.25},
                },
            },
            {
                "id": "unknown",
                "vehicle": {
                    "trip": {"trip_id": "NOT_IN_STATIC"},
                    "vehicle": {"id": "99"},
                    "timestamp": "1705880460",
                    "position": {"latitude": 53.35, "longitude": -6.25},
                },
            },
        ]
    }
    count = await RealTimeVehiclesImporter("", "", "TFI").import_vehicles(payload)
    assert count == 1
    assert await _count(rt_session_maker, RTVehicleModel, "TFI") == 1
    async with rt_session_maker() as session:
        row = await session.scalar(select(RTVehicleModel).where(RTVehicleModel.dataset == "TFI"))
    assert row is not None
    assert row.vehicle_id == 42
    assert row.trip_id == "RT_E2E_SCHED"
