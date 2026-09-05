from advanced_alchemy.base import BigIntBase, DefaultBase
from sqlalchemy import Float, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

__all__ = ["ShapeGeometryRow", "ShapeModel"]


class ShapeModel(BigIntBase):
    __tablename__ = "shape"  # type: ignore
    __table_args__ = (Index("ix_shape_shape_id_sequence", "shape_id", "sequence"),)
    shape_id: Mapped[str] = mapped_column(String(length=1000))
    lat: Mapped[float] = mapped_column(Float)
    lon: Mapped[float] = mapped_column(Float)
    sequence: Mapped[int] = mapped_column(Integer)
    distance: Mapped[float | None] = mapped_column(Float)
    dataset: Mapped[str] = mapped_column(String(length=80))


class ShapeGeometryRow(DefaultBase):
    """Polyline geometry read model: ``shape`` table without distance or dataset columns."""

    __allow_unmapped__ = True
    __table__ = ShapeModel.__table__
    __mapper_args__ = {
        "include_properties": [
            ShapeModel.__table__.c.id,
            ShapeModel.__table__.c.shape_id,
            ShapeModel.__table__.c.lat,
            ShapeModel.__table__.c.lon,
            ShapeModel.__table__.c.sequence,
        ],
    }
    id: Mapped[int]
    shape_id: Mapped[str]
    lat: Mapped[float]
    lon: Mapped[float]
    sequence: Mapped[int]
