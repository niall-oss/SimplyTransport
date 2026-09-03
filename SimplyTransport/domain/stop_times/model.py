from datetime import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..stop.model import StopModel
    from ..trip.model import TripModel

from advanced_alchemy.base import BigIntAuditBase
from sqlalchemy import ForeignKey, Integer, String, Time
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..enums import DropoffType, PickupType, Timepoint

__all__ = ["StopTimeModel"]


class StopTimeModel(BigIntAuditBase):
    __tablename__: str = "stop_time"  # type: ignore[assignment]
    trip_id: Mapped[str] = mapped_column(
        String(length=1000), ForeignKey("trip.id", ondelete="CASCADE"), index=True
    )
    trip: Mapped[TripModel] = relationship(back_populates="stop_times")
    arrival_time: Mapped[time] = mapped_column(Time)
    departure_time: Mapped[time] = mapped_column(Time)
    stop_id: Mapped[str] = mapped_column(ForeignKey("stop.id"), index=True)
    stop: Mapped[StopModel] = relationship(back_populates="stop_times")
    stop_sequence: Mapped[int] = mapped_column(Integer)
    stop_headsign: Mapped[str | None] = mapped_column(String(length=1000))
    pickup_type: Mapped[PickupType | None] = mapped_column(Integer)
    dropoff_type: Mapped[DropoffType | None] = mapped_column(Integer)
    timepoint: Mapped[Timepoint | None] = mapped_column(Integer)
    dataset: Mapped[str] = mapped_column(String(length=80))

    def is_active_between_times(self, start_time: time, end_time: time) -> bool:
        """True if arrival_time falls between the two times."""
        return start_time <= self.arrival_time <= end_time
