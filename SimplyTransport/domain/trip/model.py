from typing import TYPE_CHECKING

from advanced_alchemy.base import BigIntBase
from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, foreign, mapped_column, relationship

from ..enums import Direction

if TYPE_CHECKING:
    from SimplyTransport.domain.calendar.model import CalendarModel
    from SimplyTransport.domain.realtime.stop_time.model import RTStopTimeModel
    from SimplyTransport.domain.realtime.trip.model import RTTripModel
    from SimplyTransport.domain.realtime.vehicle.model import RTVehicleModel
    from SimplyTransport.domain.route.model import RouteModel
    from SimplyTransport.domain.stop_times.model import StopTimeModel

__all__ = ["Direction", "TripModel"]


class TripModel(BigIntBase):
    __tablename__ = "trip"  # type: ignore

    id: Mapped[str] = mapped_column(String(length=1000), primary_key=True)
    route_id: Mapped[str] = mapped_column(String(length=1000), index=True)
    route: Mapped[RouteModel] = relationship(
        back_populates="trips",
        primaryjoin=lambda: foreign(TripModel.route_id) == RouteModel.id,
        foreign_keys=[route_id],
    )
    service_id: Mapped[str] = mapped_column(String(length=1000), index=True)
    service: Mapped[CalendarModel] = relationship(
        back_populates="trips",
        primaryjoin=lambda: foreign(TripModel.service_id) == CalendarModel.id,
        foreign_keys=[service_id],
    )
    stop_times: Mapped[list[StopTimeModel]] = relationship(
        back_populates="trip",
        primaryjoin=lambda: TripModel.id == foreign(StopTimeModel.trip_id),
        foreign_keys=lambda: [StopTimeModel.trip_id],
    )
    headsign: Mapped[str | None] = mapped_column(String(length=1000))
    short_name: Mapped[str | None] = mapped_column(String(length=1000))
    direction: Mapped[Direction] = mapped_column(Integer)
    block_id: Mapped[str | None] = mapped_column(String(length=1000))
    shape_id: Mapped[str] = mapped_column(String(length=1000), index=True)
    rt_trips: Mapped[list[RTTripModel]] = relationship(back_populates="trip")
    rt_stop_times: Mapped[list[RTStopTimeModel]] = relationship(back_populates="trip")
    rt_vehicles: Mapped[list[RTVehicleModel]] = relationship(back_populates="trip")
    dataset: Mapped[str] = mapped_column(String(length=80), index=True)


from SimplyTransport.domain.calendar.model import CalendarModel as CalendarModel  # noqa: E402
from SimplyTransport.domain.route.model import RouteModel as RouteModel  # noqa: E402
from SimplyTransport.domain.stop_times.model import StopTimeModel as StopTimeModel  # noqa: E402
