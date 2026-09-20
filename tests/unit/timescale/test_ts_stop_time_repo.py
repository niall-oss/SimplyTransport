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
async def test_delete_old_delays_deletes_by_timestamp():
    session = AsyncMock()
    result = MagicMock()
    result.rowcount = 5
    session.execute = AsyncMock(return_value=result)
    session.commit = AsyncMock()
    repo = _repo(session)
    deleted = await repo.delete_old_delays(datetime(2020, 1, 1))
    assert deleted == 5
    session.execute.assert_awaited_once()
    session.commit.assert_awaited_once()
    compiled = session.execute.await_args.args[0].compile()
    sql = str(compiled)
    assert "DELETE FROM ts_stop_times" in sql
    assert 'ts_stop_times."Timestamp" <' in sql
    assert "id IN" not in sql
    assert datetime(2020, 1, 1) in compiled.params.values()


@pytest.mark.asyncio
async def test_bulk_insert_delay_records_noops_on_empty():
    session = AsyncMock()
    repo = _repo(session)
    await repo.bulk_insert_delay_records([])
    session.execute.assert_not_called()
