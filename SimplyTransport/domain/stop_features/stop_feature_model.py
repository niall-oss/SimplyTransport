from datetime import datetime
from typing import TYPE_CHECKING

from advanced_alchemy.base import BigIntAuditBase
from pydantic import BaseModel as _BaseModel
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from ..stop.stop_model import StopModel

from ..enums import Bearing, StopType


class BaseModel(_BaseModel):
    """Extend Pydantic's BaseModel to enable ORM mode"""

    model_config = {"from_attributes": True}


class StopFeatureModel(BigIntAuditBase):
    __tablename__: str = "stop_feature"  # type: ignore[assignment]

    # https://data.gov.ie/dataset/70c5967e-4df7-4dc8-82bb-c7e2b0e00888/resource/46702e02-79ac-456b-a3a9-d6cbd3c04abb/download/ptimsglossary.pdf
    # STOPS
    stop_id: Mapped[str] = mapped_column(
        String(length=1000), ForeignKey("stop.id", ondelete="CASCADE"), index=True
    )
    stop: Mapped[StopModel] = relationship(back_populates="stop_feature")
    stop_name_ie: Mapped[str | None] = mapped_column(String(length=1000))
    stop_type: Mapped[StopType | None] = mapped_column(String(length=20))
    bearing: Mapped[Bearing | None] = mapped_column(String(length=2))
    nptg_locality_ref: Mapped[str | None] = mapped_column(String(length=1000))
    bays: Mapped[int | None] = mapped_column(Integer)
    standing_area: Mapped[bool | None] = mapped_column(Boolean)
    bike_stand: Mapped[bool | None] = mapped_column(Boolean)
    bench: Mapped[bool | None] = mapped_column(Boolean)
    bin: Mapped[bool | None] = mapped_column(Boolean)
    stop_accessability: Mapped[bool | None] = mapped_column(Boolean)
    wheelchair_accessability: Mapped[bool | None] = mapped_column(Boolean)
    castle_kerbing: Mapped[bool | None] = mapped_column(Boolean)
    footpath_to_stop: Mapped[bool | None] = mapped_column(Boolean)
    step_at_stop: Mapped[bool | None] = mapped_column(Boolean)
    bike_lane_front: Mapped[bool | None] = mapped_column(Boolean)
    bike_lane_rear: Mapped[bool | None] = mapped_column(Boolean)
    surveyed: Mapped[bool | None] = mapped_column(Boolean)
    ud_surveyor: Mapped[str | None] = mapped_column(String(length=1000))
    ud_calculated: Mapped[str | None] = mapped_column(String(length=100))
    # RTPI
    rtpi_active: Mapped[bool] = mapped_column(Boolean, default=False)
    lines: Mapped[str | None] = mapped_column(String(length=1000))
    integrated_into_shelter: Mapped[bool | None] = mapped_column(Boolean)
    last_updated_rtpi: Mapped[datetime | None] = mapped_column(DateTime)
    # SHELTERS
    shelter_active: Mapped[bool] = mapped_column(Boolean, default=False)
    shelter_description: Mapped[str | None] = mapped_column(String(length=1000))
    shelter_type: Mapped[int | None] = mapped_column(Integer)
    power: Mapped[bool | None] = mapped_column(Boolean)
    light: Mapped[bool | None] = mapped_column(Boolean)
    last_updated_shelter: Mapped[datetime | None] = mapped_column(DateTime)
    # POLES
    pole_active: Mapped[bool] = mapped_column(Boolean, default=False)
    position: Mapped[str | None] = mapped_column(String(length=1000))
    pole_type: Mapped[str | None] = mapped_column(String(length=1000))
    socket_type: Mapped[str | None] = mapped_column(String(length=1000))
    last_updated_pole: Mapped[datetime | None] = mapped_column(DateTime)

    dataset: Mapped[str] = mapped_column(String(length=1000), index=True)

    def pretty_string(self, attr_name):
        value = getattr(self, attr_name, None)
        if value is None:
            return "None"
        elif isinstance(value, bool):
            return str(value)
        elif isinstance(value, datetime):
            return value.strftime("%Y-%m-%d")  # Modify this to your preferred format
        else:
            return str(value)


class StopFeature(BaseModel):
    stop_id: str
    stop_name_ie: str | None
    stop_type: StopType | None
    bearing: Bearing | None
    nptg_locality_ref: str | None
    bays: int | None
    standing_area: bool | None
    bike_stand: bool | None
    bench: bool | None
    bin: bool | None
    stop_accessability: bool | None
    wheelchair_accessability: bool | None
    castle_kerbing: bool | None
    footpath_to_stop: bool | None
    step_at_stop: bool | None
    bike_lane_front: bool | None
    bike_lane_rear: bool | None
    surveyed: bool | None
    ud_surveyor: str | None
    ud_calculated: str | None
    rtpi_active: bool | None
    lines: str | None
    integrated_into_shelter: bool | None
    last_updated_rtpi: datetime | None
    shelter_active: bool | None
    shelter_description: str | None
    shelter_type: int | None
    power: bool | None
    light: bool | None
    last_updated_shelter: datetime | None
    pole_active: bool | None
    position: str | None
    pole_type: str | None
    socket_type: str | None
    last_updated_pole: datetime | None
    dataset: str
