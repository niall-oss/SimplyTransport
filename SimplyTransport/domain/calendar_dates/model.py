from datetime import date as datetype
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..calendar.model import CalendarModel

from advanced_alchemy.base import BigIntBase
from sqlalchemy import Date, String
from sqlalchemy.orm import Mapped, foreign, mapped_column, relationship

from ..enums import ExceptionType

__all__ = ["CalendarDateModel"]


class CalendarDateModel(BigIntBase):
    __tablename__: str = "calendar_date"  # type: ignore[assignment]

    service_id: Mapped[str] = mapped_column(String(length=1000), index=True)
    service: Mapped[CalendarModel] = relationship(
        back_populates="calendar_dates",
        primaryjoin=lambda: foreign(CalendarDateModel.service_id) == CalendarModel.id,
        foreign_keys=[service_id],
    )
    date: Mapped[datetype] = mapped_column(Date)
    exception_type: Mapped[ExceptionType] = mapped_column("exception_type", String(length=20))
    dataset: Mapped[str] = mapped_column(String(length=80))


from ..calendar.model import CalendarModel as CalendarModel  # noqa: E402
