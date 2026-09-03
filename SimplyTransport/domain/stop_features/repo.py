from advanced_alchemy.repository import SQLAlchemyAsyncRepository
from litestar.di import NamedDependency
from sqlalchemy.ext.asyncio import AsyncSession

from .model import StopFeatureModel


class StopFeatureRepository(SQLAlchemyAsyncRepository[StopFeatureModel]):  # type: ignore[type-var]
    """Stop Feature repository."""

    model_type = StopFeatureModel


async def provide_stop_feature_repo(db_session: NamedDependency[AsyncSession]) -> StopFeatureRepository:
    """This provides the Stop Feature repository."""

    return StopFeatureRepository(session=db_session)
