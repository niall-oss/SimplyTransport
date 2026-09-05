import json
from datetime import datetime, timedelta
from typing import Any

from advanced_alchemy.base import BigIntAuditBase
from sqlalchemy import DateTime, Index, String, desc
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ...lib.time_date_conversions import DateTimeEncoderForJson
from .event_types import EventType

__all__ = ["EventModel"]


class EventModel(BigIntAuditBase):
    __tablename__: str = "event"  # type: ignore[assignment]
    __table_args__ = (
        Index("ix_event_created_at", "created_at"),
        Index("ix_event_event_type_created_at", "event_type", desc("created_at")),
    )

    event_type: Mapped[EventType] = mapped_column(String(length=255))
    description: Mapped[str] = mapped_column(String(length=1000))
    expiry_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    attributes: Mapped[dict] = mapped_column(JSONB)

    def to_dict(self, exclude: set[str] | None = None) -> dict[str, Any]:
        if exclude is None:
            exclude = set()
        exclude.add("updated_at")
        return super().to_dict(exclude=exclude)

    def to_json(self, indent: int = 4) -> str:
        return json.dumps(self.to_dict(), cls=DateTimeEncoderForJson, indent=indent)

    def add_pretty_created_at(self, current_time: datetime):
        """Adds a created_at_pretty to an event"""
        if self.created_at.date() == current_time.date():
            self.created_at_pretty = "Today - " + self.created_at.strftime("%H:%M")
        elif self.created_at.date() == (current_time - timedelta(days=1)).date():
            self.created_at_pretty = "Yesterday - " + self.created_at.strftime("%H:%M")
        else:
            self.created_at_pretty = self.created_at.strftime("%d %b - %H:%M")
        return self
