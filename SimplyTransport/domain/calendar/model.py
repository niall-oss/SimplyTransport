from datetime import date
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..calendar_dates.model import CalendarDateModel
    from ..trip.model import TripModel

from advanced_alchemy.base import BigIntBase
from sqlalchemy import Date, Integer, String
from sqlalchemy.orm import Mapped, foreign, mapped_column, relationship

__all__ = ["CalendarModel"]


class CalendarModel(BigIntBase):
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
        back_populates="service",
        cascade="all, delete",
        primaryjoin=lambda: CalendarModel.id == foreign(CalendarDateModel.service_id),
        foreign_keys=lambda: [CalendarDateModel.service_id],
    )
    trips: Mapped[list[TripModel]] = relationship(
        back_populates="service",
        primaryjoin=lambda: CalendarModel.id == foreign(TripModel.service_id),
        foreign_keys=lambda: [TripModel.service_id],
    )

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


from ..calendar_dates.model import CalendarDateModel as CalendarDateModel  # noqa: E402
from ..trip.model import TripModel as TripModel  # noqa: E402
