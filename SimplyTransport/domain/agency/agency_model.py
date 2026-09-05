from typing import TYPE_CHECKING

from advanced_alchemy.base import BigIntBase
from sqlalchemy import String
from sqlalchemy.orm import Mapped, foreign, mapped_column, relationship

if TYPE_CHECKING:
    from SimplyTransport.domain.route.route_model import RouteModel

__all__ = ["AgencyModel"]


class AgencyModel(BigIntBase):
    __tablename__ = "agency"  # type: ignore

    id: Mapped[str] = mapped_column(String(length=1000), primary_key=True)
    name: Mapped[str] = mapped_column(String(length=1000))
    url: Mapped[str] = mapped_column(String(length=1000))
    timezone: Mapped[str] = mapped_column(String(length=1000))
    dataset: Mapped[str] = mapped_column(String(length=80))
    routes: Mapped[list[RouteModel]] = relationship(
        back_populates="agency",
        cascade="all, delete",
        primaryjoin=lambda: AgencyModel.id == foreign(RouteModel.agency_id),
        foreign_keys=lambda: [RouteModel.agency_id],
    )

    def short_name(self):
        delimiter_list = [" – ", " / ", " - "]
        for delimiter in delimiter_list:
            if delimiter in self.name:
                try:
                    return self.name.split(delimiter)[1]
                except IndexError:
                    pass
        return self.name


from SimplyTransport.domain.route.route_model import RouteModel as RouteModel  # noqa: E402
