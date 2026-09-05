from datetime import datetime

from SimplyTransport.api_contracts.base_contracts import ApiBaseModel
from SimplyTransport.domain.events.event_types import EventType


class Event(ApiBaseModel):
    id: int
    event_type: EventType
    description: str
    expiry_time: datetime
    attributes: dict
    created_at: datetime


class EventsWithTotal(ApiBaseModel):
    total: int
    events: list[Event]
