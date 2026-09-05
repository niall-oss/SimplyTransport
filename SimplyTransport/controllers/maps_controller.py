from types import SimpleNamespace

from advanced_alchemy.exceptions import NotFoundError
from litestar import Controller, get
from litestar.di import NamedDependency, Provide
from litestar.params import FromPath
from litestar.response import Template

from ..domain.agency.agency_repo import AgencyRepo, provide_agency_repo
from ..domain.maps.enums import StaticStopMapTypes
from ..lib.logging.logging import provide_logger

__all__ = [
    "MapsController",
]

logger = provide_logger(__name__)


class MapsController(Controller):
    dependencies = {
        "agency_repo": Provide(provide_agency_repo),
    }

    @get("/agency/route/{agency_id:str}")
    async def agency_maps(
        self, agency_repo: NamedDependency[AgencyRepo], agency_id: FromPath[str]
    ) -> Template:
        if agency_id != "All":
            try:
                agency = await agency_repo.get(agency_id)
            except NotFoundError:
                return Template(
                    "maps/agency_route.html",
                    context={
                        "agency": SimpleNamespace(id=agency_id, name=agency_id),
                        "error": "Sorry, this map is not available",
                    },
                )
        else:
            agency = SimpleNamespace(id="All", name="All Agencies Combined")

        return Template("maps/agency_route.html", context={"agency": agency})

    @get("/static/agency/route/{agency_id:str}")
    async def static_agency_route_map(self, agency_id: FromPath[str]) -> Template:
        return Template("maps/static/embed_agency_route.html", context={"agency_id": agency_id})

    @get("/stop/{map_type:str}")
    async def stop_maps(self, map_type: FromPath[str]) -> Template:
        try:
            StaticStopMapTypes(map_type)
        except ValueError:
            logger.bind(map_type=map_type).error("Invalid static stop map type")
            return Template(
                "maps/stop.html",
                context={"error": "Sorry, this map is not available", "map_type": map_type},
            )

        return Template("maps/stop.html", context={"map_type": map_type})

    @get("/static/stop/{map_type:str}")
    async def static_stop_map(self, map_type: FromPath[str]) -> Template:
        return Template("maps/static/embed_stop_type.html", context={"map_type": map_type})
