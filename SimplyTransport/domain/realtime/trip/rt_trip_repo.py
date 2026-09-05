from advanced_alchemy.repository import SQLAlchemyAsyncRepository
from litestar.di import NamedDependency
from sqlalchemy.ext.asyncio import AsyncSession

from .rt_trip_model import RTTripModel


class RTTripRepo(SQLAlchemyAsyncRepository[RTTripModel]):  # type: ignore
    """RTTripRepo repository."""

    model_type = RTTripModel


async def provide_rt_trip_repo(db_session: NamedDependency[AsyncSession]) -> RTTripRepo:
    """This provides the RTTrip repository."""

    return RTTripRepo(session=db_session)
