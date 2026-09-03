from advanced_alchemy.filters import OrderBy
from litestar import Controller, get
from litestar.di import NamedDependency, Provide
from litestar.exceptions import NotFoundException
from litestar.params import FromPath

from SimplyTransport.api_contract.shape import Shape

from ...domain.shape.repo import ShapeRepository, provide_shape_repo
from ...lib.parameters.orderby_shapes import provide_order_by_shapes

__all__ = ["ShapeController"]


class ShapeController(Controller):
    dependencies = {
        "repo": Provide(provide_shape_repo),
        "order_by_shape": Provide(provide_order_by_shapes),
    }

    @get("/{shape_id:str}", summary="List of Shapes by shape Id", raises=[NotFoundException])
    async def get_shape_by_shape_id(
        self,
        repo: NamedDependency[ShapeRepository],
        shape_id: FromPath[str],
        order_by_shape: NamedDependency[OrderBy],
    ) -> list[Shape]:
        result = await repo.get_many(order_by_shape, shape_id=shape_id)
        if not result or len(result) == 0:
            raise NotFoundException(detail=f"Shapes not found with id {shape_id}")
        return [Shape.model_validate(obj) for obj in result]
