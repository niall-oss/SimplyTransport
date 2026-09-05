from typing import TYPE_CHECKING

from advanced_alchemy.base import BigIntBase
from sqlalchemy import Float, Index, Integer, String
from sqlalchemy.orm import Mapped, foreign, mapped_column, relationship

from ..enums import LocationType

if TYPE_CHECKING:
    from ..realtime.stop_time.rt_stop_time_model import RTStopTimeModel
    from ..stop_features.stop_feature_model import StopFeatureModel
    from ..stop_times.stop_time_model import StopTimeModel

__all__ = ["StopModel"]


class StopModel(BigIntBase):
    __tablename__: str = "stop"  # type: ignore[assignment]
    __table_args__ = (Index("idx_stop_coordinates", "lat", "lon"),)

    id: Mapped[str] = mapped_column(String(length=1000), primary_key=True)
    code: Mapped[str | None] = mapped_column(String(length=1000), index=True)
    name: Mapped[str] = mapped_column(String(length=1000), index=True)
    description: Mapped[str | None] = mapped_column(String(length=1000))
    lat: Mapped[float | None] = mapped_column(Float)
    lon: Mapped[float | None] = mapped_column(Float)
    zone_id: Mapped[str | None] = mapped_column(String(length=1000))
    url: Mapped[str | None] = mapped_column(String(length=1000))
    location_type: Mapped[LocationType | None] = mapped_column(Integer)
    parent_station: Mapped[str | None] = mapped_column(String(length=1000))
    stop_times: Mapped[list[StopTimeModel]] = relationship(
        back_populates="stop",
        cascade="all, delete-orphan",
        passive_deletes=True,
        primaryjoin=lambda: StopModel.id == foreign(StopTimeModel.stop_id),
        foreign_keys=lambda: [StopTimeModel.stop_id],
    )
    rt_stop_times: Mapped[list[RTStopTimeModel]] = relationship(
        back_populates="stop",
        primaryjoin=lambda: StopModel.id == foreign(RTStopTimeModel.stop_id),
        foreign_keys=lambda: [RTStopTimeModel.stop_id],
    )
    stop_feature: Mapped[StopFeatureModel] = relationship(back_populates="stop")
    dataset: Mapped[str] = mapped_column(String(length=80), index=True)


from ..realtime.stop_time.rt_stop_time_model import RTStopTimeModel as RTStopTimeModel  # noqa: E402
from ..stop_times.stop_time_model import StopTimeModel as StopTimeModel  # noqa: E402
