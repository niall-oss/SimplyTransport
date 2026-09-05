from typing import TYPE_CHECKING

from advanced_alchemy.base import BigIntBase
from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, foreign, mapped_column, relationship

from ..enums import RouteType

if TYPE_CHECKING:
    from SimplyTransport.domain.agency.agency_model import AgencyModel
    from SimplyTransport.domain.realtime.trip.rt_trip_model import RTTripModel
    from SimplyTransport.domain.trip.trip_model import TripModel

__all__ = ["RouteModel"]


class RouteModel(BigIntBase):
    __tablename__ = "route"  # type: ignore

    id: Mapped[str] = mapped_column(String(length=1000), primary_key=True)
    agency_id: Mapped[str] = mapped_column(String(length=1000), index=True)
    agency: Mapped[AgencyModel] = relationship(
        back_populates="routes",
        primaryjoin=lambda: foreign(RouteModel.agency_id) == AgencyModel.id,
        foreign_keys=[agency_id],
    )
    short_name: Mapped[str] = mapped_column(String(length=1000), index=True)
    long_name: Mapped[str] = mapped_column(String(length=1000), index=True)
    description: Mapped[str | None] = mapped_column(String(length=1000))
    route_type: Mapped[RouteType] = mapped_column(Integer)
    url: Mapped[str | None] = mapped_column(String(length=1000))
    color: Mapped[str | None] = mapped_column(String(length=1000))
    text_color: Mapped[str | None] = mapped_column(String(length=1000))
    trips: Mapped[list[TripModel]] = relationship(
        back_populates="route",
        primaryjoin=lambda: RouteModel.id == foreign(TripModel.route_id),
        foreign_keys=lambda: [TripModel.route_id],
    )
    rt_trips: Mapped[list[RTTripModel]] = relationship(
        back_populates="route",
        primaryjoin=lambda: RouteModel.id == foreign(RTTripModel.route_id),
        foreign_keys=lambda: [RTTripModel.route_id],
    )
    dataset: Mapped[str] = mapped_column(String(length=80), index=True)


from SimplyTransport.domain.agency.agency_model import AgencyModel as AgencyModel  # noqa: E402
from SimplyTransport.domain.realtime.trip.rt_trip_model import RTTripModel as RTTripModel  # noqa: E402
from SimplyTransport.domain.trip.trip_model import TripModel as TripModel  # noqa: E402
