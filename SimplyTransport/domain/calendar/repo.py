from advanced_alchemy.repository import SQLAlchemyAsyncRepository
from litestar.di import NamedDependency
from sqlalchemy.ext.asyncio import AsyncSession

from .model import CalendarModel


class CalendarRepository(SQLAlchemyAsyncRepository[CalendarModel]):  # type: ignore
    """Calendar repository."""

    model_type = CalendarModel


async def provide_calendar_repo(db_session: NamedDependency[AsyncSession]) -> CalendarRepository:
    """This provides the Calendar repository."""

    return CalendarRepository(session=db_session)
