from advanced_alchemy.repository import SQLAlchemyAsyncRepository
from litestar.di import NamedDependency
from sqlalchemy.ext.asyncio import AsyncSession

from .stop_time_model import StopTimeModel


class StopTimeRepo(SQLAlchemyAsyncRepository[StopTimeModel]):  # type: ignore[type-var]
    """StopTime repository."""

    model_type = StopTimeModel


async def provide_stop_time_repo(db_session: NamedDependency[AsyncSession]) -> StopTimeRepo:
    """This provides the StopTime repository."""

    return StopTimeRepo(session=db_session)
