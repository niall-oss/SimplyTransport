from datetime import UTC, datetime, timedelta
from typing import Literal

from advanced_alchemy.exceptions import NotFoundError
from advanced_alchemy.filters import LimitOffset, OrderBy
from advanced_alchemy.repository import SQLAlchemyAsyncRepository
from litestar.di import NamedDependency
from SimplyTransport.domain.events.event_types import EventType
from sqlalchemy import select, union_all
from sqlalchemy.ext.asyncio import AsyncSession

from ...lib.db.database import async_session_factory
from .event_model import EventModel


class EventRepo(SQLAlchemyAsyncRepository[EventModel]):  # type: ignore
    """Event repository."""

    async def create_event(
        self, event_type: EventType, description: str, attributes: dict, expiry_time: datetime | None = None
    ) -> EventModel:
        """Create event."""

        if expiry_time is None:
            # Set the default expiry
            expiry_time = datetime.now(tz=UTC) + timedelta(days=90)

        event = EventModel(
            event_type=event_type, description=description, expiry_time=expiry_time, attributes=attributes
        )
        new_event = await self.add(event)
        await self.session.commit()
        return new_event

    async def get_paginated_events_by_type_with_total(
        self,
        event_type: EventType,
        limit_offset: LimitOffset,
        order: Literal["asc", "desc"] = "desc",
    ) -> tuple[list[EventModel], int]:
        """Get paginated events by type with total."""

        results, total = await self.get_many_and_count(
            EventModel.event_type == event_type,
            OrderBy(EventModel.created_at, order),  # type: ignore
            limit_offset,
        )

        if total == 0:
            raise NotFoundError()

        return results, total

    async def get_single_pretty_event_by_type(self, event_type: EventType) -> EventModel | None:
        try:
            events = await self.get_paginated_events_by_type_with_total(
                event_type=event_type, limit_offset=LimitOffset(limit=1, offset=0), order="desc"
            )
        except NotFoundError:
            return None
        else:
            event = events[0][0]
            current_time = datetime.now(UTC)
            return event.add_pretty_created_at(current_time)

    async def get_multiple_pretty_events_by_types(
        self, event_types: list[EventType]
    ) -> dict[EventType, EventModel]:
        """Get the most recent event for each of the specified event types.

        Uses UNION ALL of per-type ``LIMIT 1`` subqueries so the planner can use
        ``(event_type, created_at DESC)`` with a short index scan per type, instead of
        ``DISTINCT ON`` over all rows matching ``IN (...)``.
        """
        if not event_types:
            return {}
        # One round-trip: ids via UNION ALL … LIMIT 1 in a subquery, then full rows by PK.
        # Avoid union of select(EventModel): scalars() would return event_type strings, not entities.
        id_selects = [
            select(EventModel.id)
            .where(EventModel.event_type == et)
            .order_by(EventModel.created_at.desc())
            .limit(1)
            for et in event_types
        ]
        ids_subq = union_all(*id_selects).subquery()
        stmt = select(EventModel).where(EventModel.id.in_(select(ids_subq.c.id)))
        result = await self.session.execute(stmt)
        events = result.scalars().all()

        current_time = datetime.now(UTC)
        return {event.event_type: event.add_pretty_created_at(current_time) for event in events}

    async def get_most_recent_event_by_type(self, event_type: EventType) -> EventModel | None:
        try:
            events = await self.get_paginated_events_by_type_with_total(
                event_type=event_type, limit_offset=LimitOffset(limit=1, offset=0), order="desc"
            )
        except NotFoundError:
            return None
        else:
            return events[0][0]

    async def get_paginated_events_with_total(
        self, limit_offset: LimitOffset, order: Literal["asc", "desc"] = "desc"
    ) -> tuple[list[EventModel], int]:
        """Get paginated events with total."""

        results, total = await self.get_many_and_count(
            OrderBy(EventModel.created_at, order),  # type: ignore
            limit_offset,
        )

        if total == 0:
            raise NotFoundError()

        return results, total

    async def get_paginated_events(
        self, limit_offset: LimitOffset, order: Literal["asc", "desc"] = "desc"
    ) -> list[EventModel]:
        """Get paginated events."""

        return await self.get_many(OrderBy(EventModel.created_at, order), limit_offset)  # type: ignore

    async def cleanup_events(self, event_type: EventType | None = None) -> int:
        """Cleanup events that have expired. If event_type is provided, only cleanup events of that type."""

        if event_type:
            events_to_delete = await self.get_many(
                EventModel.event_type == event_type, EventModel.expiry_time < datetime.now(tz=UTC)
            )
            total_events_deleted = len(events_to_delete)
            await self.delete_many([event.id for event in events_to_delete])
        else:
            events_to_delete = await self.get_many(EventModel.expiry_time < datetime.now(tz=UTC))
            total_events_deleted = len(events_to_delete)
            await self.delete_many([event.id for event in events_to_delete])
        await self.session.commit()

        return total_events_deleted

    model_type = EventModel


async def provide_event_repo(db_session: NamedDependency[AsyncSession]) -> EventRepo:
    """This provides the Event repository."""

    return EventRepo(session=db_session)


async def create_event_with_session(
    event_type: EventType, description: str, attributes: dict, expiry_time: datetime | None = None
):
    async with async_session_factory() as db_session:
        event_repo = await provide_event_repo(db_session=db_session)
        await event_repo.create_event(event_type, description, attributes, expiry_time)
