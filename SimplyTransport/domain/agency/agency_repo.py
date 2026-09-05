from advanced_alchemy.repository import SQLAlchemyAsyncRepository
from litestar.di import NamedDependency
from sqlalchemy.ext.asyncio import AsyncSession

from .agency_model import AgencyModel


class AgencyRepo(SQLAlchemyAsyncRepository[AgencyModel]):  # type: ignore
    """Agency repository."""

    model_type = AgencyModel


async def provide_agency_repo(db_session: NamedDependency[AsyncSession]) -> AgencyRepo:
    """This provides the Agency repository."""

    return AgencyRepo(session=db_session)
