from datetime import date

from advanced_alchemy.repository import SQLAlchemyAsyncRepository
from litestar.di import NamedDependency
from sqlalchemy.ext.asyncio import AsyncSession

from ..enums import ExceptionType
from .calendar_date_model import CalendarDateModel


class CalendarDateRepo(SQLAlchemyAsyncRepository[CalendarDateModel]):  # type: ignore
    """Calendar repository."""

    async def get_removed_exceptions_on_date(self, date: date) -> list[CalendarDateModel]:
        """Returns a list of removed exceptions for the given date"""

        return await self.get_many(
            CalendarDateModel.date == date,
            CalendarDateModel.exception_type == ExceptionType.removed,
        )

    async def get_added_exceptions_on_date(self, date: date) -> list[CalendarDateModel]:
        """Returns a list of added exceptions for the given date"""

        return await self.get_many(
            CalendarDateModel.date == date,
            CalendarDateModel.exception_type == ExceptionType.added,
        )

    model_type = CalendarDateModel


async def provide_calendar_date_repo(db_session: NamedDependency[AsyncSession]) -> CalendarDateRepo:
    """This provides the Calendar Date repository."""

    return CalendarDateRepo(session=db_session)
