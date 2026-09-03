import math
from datetime import UTC, datetime
from typing import Annotated, Literal

from advanced_alchemy.exceptions import NotFoundError
from advanced_alchemy.filters import LimitOffset
from litestar import Controller, get
from litestar.di import NamedDependency, Provide
from litestar.exceptions import ValidationException
from litestar.params import QueryParameter
from litestar.response import Template

from ..domain.events.event_types import EventType
from ..domain.events.repo import EventRepository, provide_event_repo
from ..lib.parameters.pagination_page_numbers import generate_pagination_pages

__all__ = [
    "EventsController",
]

ALL_EVENTS = "all.event.types"


class EventsController(Controller):
    dependencies = {
        "event_repo": Provide(provide_event_repo),
    }

    @get("/")
    async def root(self) -> Template:
        event_types = [event_type.value for event_type in EventType.__members__.values()]
        event_types.insert(0, ALL_EVENTS)

        return Template(template_name="events/events_main.html", context={"event_types": event_types})

    @get("/search")
    async def search(
        self,
        event_repo: NamedDependency[EventRepository],
        limit_offset: NamedDependency[LimitOffset],
        search_type: Annotated[
            str | None,
            QueryParameter(name="search_type", description="Search events by type"),
        ] = None,
        sort: Annotated[
            Literal["asc", "desc"],
            QueryParameter(
                name="sort",
                description="Sort events ascending or descending by creation time",
            ),
        ] = "desc",
    ) -> Template:
        if search_type is None or search_type == ALL_EVENTS:
            search_type = ALL_EVENTS
            try:
                events, total = await event_repo.get_paginated_events_with_total(
                    limit_offset=limit_offset, order=sort
                )
            except NotFoundError:
                events = []
                total = 0
        else:
            if search_type not in [event_type.value for event_type in EventType.__members__.values()]:
                raise ValidationException("Invalid event type")

            try:
                events, total = await event_repo.get_paginated_events_by_type_with_total(
                    event_type=EventType(search_type), limit_offset=limit_offset, order=sort
                )
            except NotFoundError:
                events = []
                total = 0

        current_time = datetime.now(UTC)
        events = [event.add_pretty_created_at(current_time) for event in events]

        current_page = limit_offset.offset // limit_offset.limit + 1
        total_pages = math.ceil(total / limit_offset.limit)
        pages = generate_pagination_pages(current_page, total_pages)

        return Template(
            template_name="events/list_of_events.html",
            context={
                "events": events,
                "search_type": search_type,
                "sort": sort,
                "limit": limit_offset.limit,
                "current_page": current_page,
                "total_pages": total_pages,
                "total": total,
                "pages": pages,
            },
        )
