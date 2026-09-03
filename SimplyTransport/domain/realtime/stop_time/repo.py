from advanced_alchemy.repository import SQLAlchemyAsyncRepository
from litestar.di import NamedDependency
from sqlalchemy.ext.asyncio import AsyncSession

from .model import RTStopTimeModel


class RTStopTimeRepository(SQLAlchemyAsyncRepository[RTStopTimeModel]):  # type: ignore
    """RTStopTime repository."""

    model_type = RTStopTimeModel


async def provide_rt_stop_time_repo(db_session: NamedDependency[AsyncSession]) -> RTStopTimeRepository:
    """This provides the RTStopTime repository."""

    return RTStopTimeRepository(session=db_session)
