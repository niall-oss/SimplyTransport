from advanced_alchemy.repository import SQLAlchemyAsyncRepository
from litestar.di import NamedDependency
from sqlalchemy.ext.asyncio import AsyncSession

from .model import AgencyModel


class AgencyRepository(SQLAlchemyAsyncRepository[AgencyModel]):  # type: ignore
    """Agency repository."""

    model_type = AgencyModel


async def provide_agency_repo(db_session: NamedDependency[AsyncSession]) -> AgencyRepository:
    """This provides the Agency repository."""

    return AgencyRepository(session=db_session)
