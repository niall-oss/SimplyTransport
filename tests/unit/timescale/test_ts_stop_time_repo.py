from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from freezegun import freeze_time
from SimplyTransport.timescale.ts_stop_times.ts_stop_time_repo import (
    TSStopTimeRepo,
    maximum_timestamp,
)


def _repo(session: AsyncMock) -> TSStopTimeRepo:
    repo = TSStopTimeRepo.__new__(TSStopTimeRepo)
    repo.session = session
    return repo


@freeze_time("2026-06-01 12:00:00")
def test_maximum_timestamp_is_computed_from_now():
    assert maximum_timestamp() == datetime(2026, 6, 1, 12, 0, 0) - timedelta(days=180)


@pytest.mark.asyncio
async def test_delete_old_delays_runs_another_batch_when_full():
    session = AsyncMock()
    full = MagicMock()
    full.rowcount = 2
    partial = MagicMock()
    partial.rowcount = 1
    session.execute = AsyncMock(side_effect=[full, partial])
    session.commit = AsyncMock()
    repo = _repo(session)
    deleted = await repo.delete_old_delays(datetime(2020, 1, 1), batch_size=2)
    assert deleted == 3
    assert session.execute.await_count == 2
    assert session.commit.await_count == 2


@pytest.mark.asyncio
async def test_bulk_insert_delay_records_noops_on_empty():
    session = AsyncMock()
    repo = _repo(session)
    await repo.bulk_insert_delay_records([])
    session.execute.assert_not_called()
