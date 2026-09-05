from unittest.mock import AsyncMock, MagicMock

import pytest
from SimplyTransport.domain.events.event_repo import EventRepo
from SimplyTransport.domain.events.event_types import EventType


@pytest.mark.asyncio
async def test_create_event_calls_add_and_commit():
    # Arrange
    session = MagicMock()
    session.commit = AsyncMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    event_repo = EventRepo(session=session)

    event_type = EventType.RECORD_TS_STOP_TIMES
    description = "description"
    attributes = {"key": "value"}

    # Act
    await event_repo.create_event(event_type, description, attributes)

    # Assert
    session.add.assert_called_once()
    session.commit.assert_called_once()
