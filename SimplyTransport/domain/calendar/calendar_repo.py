from advanced_alchemy.repository import SQLAlchemyAsyncRepository
from litestar.di import NamedDependency
from sqlalchemy.ext.asyncio import AsyncSession

from .calendar_model import CalendarModel


class CalendarRepo(SQLAlchemyAsyncRepository[CalendarModel]):  # type: ignore
    """Calendar repository."""

    model_type = CalendarModel


async def provide_calendar_repo(db_session: NamedDependency[AsyncSession]) -> CalendarRepo:
    """This provides the Calendar repository."""

    return CalendarRepo(session=db_session)
