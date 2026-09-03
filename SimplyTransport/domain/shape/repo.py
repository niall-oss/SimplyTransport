from collections.abc import Sequence

from advanced_alchemy.repository import SQLAlchemyAsyncRepository
from litestar.di import NamedDependency
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .model import ShapeGeometryRow, ShapeModel


class ShapeRepository(SQLAlchemyAsyncRepository[ShapeModel]):  # type: ignore[type-var]
    """Stop repository."""

    async def get_sequence_sorted_shapes_by_shape_id(self, shape_id: str) -> list[ShapeGeometryRow]:
        """Return shape points for one id, ordered by ``sequence`` (GTFS order)."""

        if not shape_id:
            return []

        result = await self.session.execute(
            select(ShapeGeometryRow)
            .filter(ShapeGeometryRow.shape_id == shape_id)
            .order_by(ShapeGeometryRow.sequence)
        )
        return list(result.scalars().all())

    async def get_sequence_sorted_shapes_by_shape_ids(
        self, shape_ids: list[str]
    ) -> Sequence[ShapeGeometryRow]:
        """Return shape points for the given ids, ordered by ``shape_id`` then ``sequence`` (GTFS order)."""

        if not shape_ids:
            return []

        result = await self.session.execute(
            select(ShapeGeometryRow)
            .filter(ShapeGeometryRow.shape_id.in_(shape_ids))
            .order_by(ShapeGeometryRow.shape_id, ShapeGeometryRow.sequence)
        )
        return result.scalars().all()

    model_type = ShapeModel


async def provide_shape_repo(db_session: NamedDependency[AsyncSession]) -> ShapeRepository:
    """This provides the Shape repository."""

    return ShapeRepository(session=db_session)
