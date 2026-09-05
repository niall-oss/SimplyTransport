from datetime import UTC, datetime
from typing import TYPE_CHECKING

from advanced_alchemy.base import BigIntBase
from advanced_alchemy.types.datetime import DateTimeUTC
from pydantic import BaseModel as _BaseModel
from sqlalchemy import Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, foreign, mapped_column, relationship

from ..enums import ScheduleRelationship

if TYPE_CHECKING:
    from SimplyTransport.domain.stop.stop_model import StopModel
    from SimplyTransport.domain.trip.trip_model import TripModel


class BaseModel(_BaseModel):
    """Extend Pydantic's BaseModel to enable ORM mode"""

    model_config = {"from_attributes": True}


class RTStopTimeModel(BigIntBase):
    __tablename__ = "rt_stop_time"  # type: ignore
    __table_args__ = (
        Index("ix_rt_stop_time_dataset_created_at", "dataset", "created_at"),
        UniqueConstraint(
            "stop_id", "trip_id", "stop_sequence", "dataset"
        ),  # Only store the most recent update per stop_sequence for each trip
    )

    stop: Mapped[StopModel] = relationship(
        back_populates="rt_stop_times",
        primaryjoin=lambda: foreign(RTStopTimeModel.stop_id) == StopModel.id,
        foreign_keys=lambda: [RTStopTimeModel.stop_id],
    )
    stop_id: Mapped[str] = mapped_column(String(length=1000), index=True)
    trip: Mapped[TripModel] = relationship(
        back_populates="rt_stop_times",
        primaryjoin=lambda: foreign(RTStopTimeModel.trip_id) == TripModel.id,
        foreign_keys=lambda: [RTStopTimeModel.trip_id],
    )
    trip_id: Mapped[str] = mapped_column(String(length=1000), index=True)
    stop_sequence: Mapped[int] = mapped_column(Integer)
    schedule_relationship: Mapped[ScheduleRelationship] = mapped_column(String(length=1000))
    arrival_delay: Mapped[int | None] = mapped_column(Integer)
    departure_delay: Mapped[int | None] = mapped_column(Integer)
    entity_id: Mapped[str] = mapped_column(String(length=1000))
    dataset: Mapped[str] = mapped_column(String(length=80))
    created_at: Mapped[datetime] = mapped_column(
        DateTimeUTC(timezone=True),
        default=lambda: datetime.now(UTC),
    )


class RTStopTime(BaseModel):
    stop_id: str
    trip_id: str
    stop_sequence: int
    schedule_relationship: ScheduleRelationship
    arrival_delay: int
    departure_delay: int


from SimplyTransport.domain.stop.stop_model import StopModel as StopModel  # noqa: E402
from SimplyTransport.domain.trip.trip_model import TripModel as TripModel  # noqa: E402
