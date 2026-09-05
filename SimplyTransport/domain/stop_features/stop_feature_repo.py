from advanced_alchemy.repository import SQLAlchemyAsyncRepository
from litestar.di import NamedDependency
from sqlalchemy.ext.asyncio import AsyncSession

from .stop_feature_model import StopFeatureModel


class StopFeatureRepo(SQLAlchemyAsyncRepository[StopFeatureModel]):  # type: ignore[type-var]
    """Stop Feature repository."""

    model_type = StopFeatureModel


async def provide_stop_feature_repo(db_session: NamedDependency[AsyncSession]) -> StopFeatureRepo:
    """This provides the Stop Feature repository."""

    return StopFeatureRepo(session=db_session)
