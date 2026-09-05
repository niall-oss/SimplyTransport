from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest
from litestar.testing import AsyncTestClient
from SimplyTransport.domain.realtime.realtime_schedule.realtime_schedule_repo import RealtimeScheduleRepo
from SimplyTransport.domain.realtime.stop_time.rt_stop_time_model import RTStopTimeModel
from SimplyTransport.domain.schedule.static_schedule_model import StaticScheduleModel
from SimplyTransport.lib import settings
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

pytestmark = pytest.mark.asyncio(loop_scope="session")


def _static(stop_id: str, sequence: int) -> StaticScheduleModel:
    stop_time = MagicMock()
    stop_time.stop_sequence = sequence
    stop = MagicMock()
    stop.id = stop_id
    trip = MagicMock()
    trip.id = "RT_E2E_SCHED"
    trip.dataset = "TFI"
    return StaticScheduleModel(
        route=MagicMock(),
        stop_time=stop_time,
        calendar=MagicMock(),
        stop=stop,
        trip=trip,
        is_added_exception=False,
    )


async def test_load_recent_overlay_ignores_rows_older_than_30_minutes(
    async_client: AsyncTestClient,
) -> None:
    engine = create_async_engine(settings.app.DB_URL, pool_pre_ping=True)
    try:
        session_maker = async_sessionmaker(engine, expire_on_commit=False)
        now = datetime.now(UTC)
        async with session_maker() as session:
            session.add(
                RTStopTimeModel(
                    stop_id="RT_E2E_S1",
                    trip_id="RT_E2E_SCHED",
                    stop_sequence=99,
                    schedule_relationship="SCHEDULED",
                    arrival_delay=111,
                    departure_delay=111,
                    entity_id="overlay-old",
                    dataset="TFI",
                    created_at=now - timedelta(minutes=31),
                )
            )
            session.add(
                RTStopTimeModel(
                    stop_id="RT_E2E_S2",
                    trip_id="RT_E2E_SCHED",
                    stop_sequence=2,
                    schedule_relationship="SCHEDULED",
                    arrival_delay=42,
                    departure_delay=42,
                    entity_id="overlay-new",
                    dataset="TFI",
                    created_at=now - timedelta(minutes=1),
                )
            )
            await session.commit()

            repo = RealtimeScheduleRepo(session=session)
            _trips, stops = await repo.load_recent_rt_overlay_for_schedules(
                [_static("RT_E2E_S2", 2), _static("RT_E2E_S1", 50)]
            )

        recent = stops[("RT_E2E_SCHED", "RT_E2E_S2", 2)]
        assert recent.exact_match is True
        assert recent.row.arrival_delay == 42
        assert all(overlay.row.stop_sequence != 99 for overlay in stops.values())
    finally:
        await engine.dispose()
