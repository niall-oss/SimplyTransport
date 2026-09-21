from collections.abc import AsyncIterator
from datetime import time

import pytest
import pytest_asyncio
from freezegun import freeze_time
from SimplyTransport.domain.services.realtime_service import provide_realtime_service
from SimplyTransport.domain.services.schedule_service import provide_schedule_service
from SimplyTransport.lib import settings
from SimplyTransport.lib.cache import RedisService
from SimplyTransport.timescale.services.delays_service import DelaysService, delay_recording_cache_key
from SimplyTransport.timescale.ts_stop_times.ts_stop_time_model import TSStopTimeModel
from SimplyTransport.timescale.ts_stop_times.ts_stop_time_repo import TSStopTimeRepo
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

pytestmark = pytest.mark.asyncio(loop_scope="session")

E2E_STOP = "RT_E2E_S1"
E2E_ROUTE = "4"
E2E_TIME = time(12, 0)
E2E_CANCEL_TIME = time(12, 10)
E2E_KEY = delay_recording_cache_key(E2E_ROUTE, E2E_STOP, E2E_TIME)


type SessionMaker = async_sessionmaker[AsyncSession]


@pytest_asyncio.fixture(loop_scope="session")
async def delay_sessions(test_stack: None) -> AsyncIterator[tuple[SessionMaker, SessionMaker]]:
    pg_engine: AsyncEngine = create_async_engine(settings.app.DB_URL, pool_pre_ping=True)
    ts_engine: AsyncEngine = create_async_engine(settings.app.TIMESCALE_URL, pool_pre_ping=True)
    pg_sessions: SessionMaker = async_sessionmaker(pg_engine, expire_on_commit=False)
    ts_sessions: SessionMaker = async_sessionmaker(ts_engine, expire_on_commit=False)
    try:
        yield pg_sessions, ts_sessions
    finally:
        await pg_engine.dispose()
        await ts_engine.dispose()


def _e2e_row_filter():
    return (
        TSStopTimeModel.stop_id == E2E_STOP,
        TSStopTimeModel.route_code == E2E_ROUTE,
        TSStopTimeModel.scheduled_time == E2E_TIME,
    )


async def _count_e2e_delay_rows(ts_sessions: SessionMaker) -> int:
    async with ts_sessions() as session:
        result = await session.scalar(
            select(func.count()).select_from(TSStopTimeModel).where(*_e2e_row_filter())
        )
        return int(result or 0)


async def _fetch_e2e_delay_row(ts_sessions: SessionMaker) -> TSStopTimeModel | None:
    async with ts_sessions() as session:
        return await session.scalar(select(TSStopTimeModel).where(*_e2e_row_filter()))


async def _clear_e2e_delay_state(ts_sessions: SessionMaker) -> None:
    async with ts_sessions() as session:
        await session.execute(delete(TSStopTimeModel).where(*_e2e_row_filter()))
        await session.execute(
            delete(TSStopTimeModel).where(
                TSStopTimeModel.stop_id == E2E_STOP,
                TSStopTimeModel.route_code == E2E_ROUTE,
                TSStopTimeModel.scheduled_time == E2E_CANCEL_TIME,
            )
        )
        await session.commit()
    async with RedisService() as redis:
        await redis.delete_key(E2E_KEY)


async def _record(pg_sessions: SessionMaker, ts_sessions: SessionMaker) -> int:
    async with pg_sessions() as db_session, ts_sessions() as ts_session, RedisService() as redis:
        service = DelaysService(
            ts_stop_time_repo=TSStopTimeRepo(session=ts_session),
            schedule_service=await provide_schedule_service(db_session=db_session),
            realtime_service=await provide_realtime_service(db_session=db_session),
            redis_cache=redis,
        )
        return await service.record_all_delays()


@freeze_time("2025-03-21 12:06:30")
async def test_record_all_delays_inserts_due_row_then_skips_redis_hit(
    delay_sessions: tuple[SessionMaker, SessionMaker],
) -> None:
    pg_sessions, ts_sessions = delay_sessions
    await _clear_e2e_delay_state(ts_sessions)

    await _record(pg_sessions, ts_sessions)
    assert await _count_e2e_delay_rows(ts_sessions) == 1
    row = await _fetch_e2e_delay_row(ts_sessions)
    assert row is not None
    assert row.delay_in_seconds == 360
    assert row.route_code == E2E_ROUTE
    async with RedisService() as redis:
        keys = await redis.check_keys_exist([E2E_KEY])
    assert keys.get(E2E_KEY) is True

    await _record(pg_sessions, ts_sessions)
    assert await _count_e2e_delay_rows(ts_sessions) == 1

    await _clear_e2e_delay_state(ts_sessions)


@freeze_time("2025-03-21 12:10:30")
async def test_record_all_delays_skips_cancelled_trip(
    delay_sessions: tuple[SessionMaker, SessionMaker],
) -> None:
    pg_sessions, ts_sessions = delay_sessions
    await _clear_e2e_delay_state(ts_sessions)
    await _record(pg_sessions, ts_sessions)
    assert await _count_e2e_delay_rows(ts_sessions) == 0
    async with ts_sessions() as session:
        cancelled = await session.scalar(
            select(func.count())
            .select_from(TSStopTimeModel)
            .where(
                TSStopTimeModel.stop_id == E2E_STOP,
                TSStopTimeModel.route_code == E2E_ROUTE,
                TSStopTimeModel.scheduled_time == E2E_CANCEL_TIME,
            )
        )
    assert int(cancelled or 0) == 0
