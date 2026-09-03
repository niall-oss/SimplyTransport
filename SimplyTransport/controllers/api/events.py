from typing import Annotated, Literal

from advanced_alchemy.filters import LimitOffset
from litestar import Controller, get
from litestar.di import NamedDependency, Provide
from litestar.exceptions import NotFoundException
from litestar.params import FromPath, QueryParameter

from SimplyTransport.api_contract.events import Event, EventsWithTotal
from SimplyTransport.domain.events.event_types import EventType

from ...domain.events.repo import EventRepository, provide_event_repo

__all__ = ["EventsController"]


class EventsController(Controller):
    dependencies = {"repo": Provide(provide_event_repo)}

    @get(
        "/",
        summary="Get paginated events",
        raises=[NotFoundException],
    )
    async def get_events(
        self,
        repo: NamedDependency[EventRepository],
        limit_offset: NamedDependency[LimitOffset],
        order: Annotated[
            Literal["desc", "asc"],
            QueryParameter(description="Order by descending or ascending"),
        ] = "desc",
    ) -> EventsWithTotal:
        result, total = await repo.get_paginated_events_with_total(limit_offset, order)

        if not result:
            raise NotFoundException(detail="Events not found")

        return EventsWithTotal(total=total, events=[Event.model_validate(obj) for obj in result])

    @get(
        "/{type:str}",
        summary="Get paginated events by type",
        raises=[NotFoundException],
    )
    async def get_events_by_type(
        self,
        repo: NamedDependency[EventRepository],
        type: FromPath[EventType],
        limit_offset: NamedDependency[LimitOffset],
        order: Annotated[
            Literal["desc", "asc"],
            QueryParameter(description="Order by descending or ascending"),
        ] = "desc",
    ) -> EventsWithTotal:
        result, total = await repo.get_paginated_events_by_type_with_total(type, limit_offset, order)

        if not result:
            raise NotFoundException(detail=f"Events not found for {type.value}")

        return EventsWithTotal(total=total, events=[Event.model_validate(obj) for obj in result])

    @get(
        "/{type:str}/most-recent",
        summary="Get most recent event by type",
        raises=[NotFoundException],
    )
    async def get_most_recent_event_by_type(
        self,
        repo: NamedDependency[EventRepository],
        type: FromPath[EventType],
    ) -> Event:
        result = await repo.get_most_recent_event_by_type(type)

        if result is None:
            raise NotFoundException(detail=f"Events not found for {type.value}")

        return Event.model_validate(result)
