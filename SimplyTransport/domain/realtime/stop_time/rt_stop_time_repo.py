from advanced_alchemy.repository import SQLAlchemyAsyncRepository
from litestar.di import NamedDependency
from sqlalchemy.ext.asyncio import AsyncSession

from .rt_stop_time_model import RTStopTimeModel


class RTStopTimeRepo(SQLAlchemyAsyncRepository[RTStopTimeModel]):  # type: ignore
    """RTStopTime repository."""

    model_type = RTStopTimeModel


async def provide_rt_stop_time_repo(db_session: NamedDependency[AsyncSession]) -> RTStopTimeRepo:
    """This provides the RTStopTime repository."""

    return RTStopTimeRepo(session=db_session)
