from datetime import UTC, date, datetime, time
from typing import TYPE_CHECKING

from advanced_alchemy.base import BigIntBase
from advanced_alchemy.types.datetime import DateTimeUTC
from pydantic import BaseModel as _BaseModel
from pydantic import Field
from sqlalchemy import Date, Index, Integer, String, Time, UniqueConstraint
from sqlalchemy.orm import Mapped, foreign, mapped_column, relationship

if TYPE_CHECKING:
    from ...route.model import RouteModel
    from ...trip.model import TripModel

from ...enums import Direction
from ..enums import ScheduleRealtionship


class BaseModel(_BaseModel):
    """Extend Pydantic's BaseModel to enable ORM mode"""

    model_config = {"from_attributes": True}


class RTTripModel(BigIntBase):
    __tablename__ = "rt_trip"  # type: ignore
    __table_args__ = (
        Index("ix_rt_trip_dataset_created_at", "dataset", "created_at"),
        UniqueConstraint(
            "trip_id", "route_id", "dataset"
        ),  # Only store the most recent update per trip for each route
    )

    trip: Mapped[TripModel] = relationship(
        back_populates="rt_trips",
        primaryjoin=lambda: foreign(RTTripModel.trip_id) == TripModel.id,
        foreign_keys=lambda: [RTTripModel.trip_id],
    )
    trip_id: Mapped[str] = mapped_column(String(length=1000), index=True)
    route: Mapped[RouteModel] = relationship(
        back_populates="rt_trips",
        primaryjoin=lambda: foreign(RTTripModel.route_id) == RouteModel.id,
        foreign_keys=lambda: [RTTripModel.route_id],
    )
    route_id: Mapped[str] = mapped_column(String(length=1000), index=True)
    start_time: Mapped[time] = mapped_column(Time)
    start_date: Mapped[date] = mapped_column(Date)
    schedule_relationship: Mapped[ScheduleRealtionship] = mapped_column(String(length=1000))
    direction: Mapped[Direction] = mapped_column(Integer)
    entity_id: Mapped[str] = mapped_column(String(length=1000))
    dataset: Mapped[str] = mapped_column(String(length=80))
    created_at: Mapped[datetime] = mapped_column(
        DateTimeUTC(timezone=True),
        default=lambda: datetime.now(UTC),
    )


class RTTrip(BaseModel):
    trip_id: str
    route_id: str
    start_time: time
    start_date: date
    schedule_relationship: ScheduleRealtionship
    direction: Direction = Field(description="Direction of travel. Mapping between agencies could differ.")


from SimplyTransport.domain.route.model import RouteModel as RouteModel  # noqa: E402
from SimplyTransport.domain.trip.model import TripModel as TripModel  # noqa: E402
