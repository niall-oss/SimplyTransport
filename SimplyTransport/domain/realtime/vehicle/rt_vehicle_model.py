from datetime import UTC, datetime
from typing import TYPE_CHECKING

from advanced_alchemy.base import BigIntBase
from advanced_alchemy.types.datetime import DateTimeUTC
from pydantic import BaseModel as _BaseModel
from sqlalchemy import DateTime, Float, Index, Integer, String
from sqlalchemy.orm import Mapped, foreign, mapped_column, relationship

if TYPE_CHECKING:
    from SimplyTransport.domain.trip.trip_model import TripModel


class BaseModel(_BaseModel):
    """Extend Pydantic's BaseModel to enable ORM mode"""

    model_config = {"from_attributes": True}


class RTVehicleModel(BigIntBase):
    __tablename__ = "rt_vehicle"  # type: ignore
    __table_args__ = (Index("ix_rt_vehicle_dataset_created_at", "dataset", "created_at"),)

    vehicle_id: Mapped[int] = mapped_column(Integer)
    trip: Mapped[TripModel] = relationship(
        back_populates="rt_vehicles",
        primaryjoin=lambda: foreign(RTVehicleModel.trip_id) == TripModel.id,
        foreign_keys=lambda: [RTVehicleModel.trip_id],
    )
    trip_id: Mapped[str] = mapped_column(String(length=1000), index=True)
    time_of_update: Mapped[datetime] = mapped_column(DateTime)
    lat: Mapped[float] = mapped_column(Float)
    lon: Mapped[float] = mapped_column(Float)
    dataset: Mapped[str] = mapped_column(String(length=80))
    created_at: Mapped[datetime] = mapped_column(
        DateTimeUTC(timezone=True),
        default=lambda: datetime.now(UTC),
    )

    def mins_ago_updated(self) -> str:
        """Returns the number of minutes ago the vehicle was updated."""
        mins = (datetime.now() - self.time_of_update).seconds // 60
        if mins == 0:
            return "Less than a minute ago"
        if mins == 1:
            return "1 min ago"
        return f"{mins} mins ago"


class RTVehicle(BaseModel):
    vehicle_id: int
    trip_id: str
    time_of_update: datetime
    lat: float
    lon: float
    dataset: str


from SimplyTransport.domain.trip.trip_model import TripModel as TripModel  # noqa: E402
