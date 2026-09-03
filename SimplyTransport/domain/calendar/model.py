from datetime import date
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..trip.model import TripModel

from advanced_alchemy.base import BigIntAuditBase
from sqlalchemy import Date, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..calendar_dates.model import CalendarDateModel

__all__ = ["CalendarModel"]


class CalendarModel(BigIntAuditBase):
    __tablename__: str = "calendar"  # type: ignore[assignment]

    id: Mapped[str] = mapped_column(String(length=1000), primary_key=True)
    monday: Mapped[int] = mapped_column(Integer)
    tuesday: Mapped[int] = mapped_column(Integer)
    wednesday: Mapped[int] = mapped_column(Integer)
    thursday: Mapped[int] = mapped_column(Integer)
    friday: Mapped[int] = mapped_column(Integer)
    saturday: Mapped[int] = mapped_column(Integer)
    sunday: Mapped[int] = mapped_column(Integer)
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    dataset: Mapped[str] = mapped_column(String(length=80))
    calendar_dates: Mapped[list[CalendarDateModel]] = relationship(
        back_populates="service", cascade="all, delete"
    )
    trips: Mapped[list[TripModel]] = relationship(back_populates="service")

    def is_active_on_date(self, date: date) -> bool:
        """True when this regular service runs on the date (range and weekday)."""
        if not (self.start_date <= date <= self.end_date):
            return False
        weekday_flags = (
            self.monday,
            self.tuesday,
            self.wednesday,
            self.thursday,
            self.friday,
            self.saturday,
            self.sunday,
        )
        return weekday_flags[date.weekday()] == 1
