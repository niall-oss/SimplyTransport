from litestar import Controller, Response, get
from litestar.di import NamedDependency, Provide
from litestar.exceptions import HTTPException
from litestar.response import File, Template

from ..domain.agency.model import AgencyModel
from ..domain.agency.repo import AgencyRepository, provide_agency_repo
from ..domain.events.event_types import EventType
from ..domain.events.repo import EventRepository, provide_event_repo
from ..domain.maps.enums import StaticStopMapTypes
from ..lib.constants import APP_DIR, STATIC_DIR
from ..lib.db.services import test_database_connections
from ..lib.logging.logging import provide_logger

__all__ = [
    "RootController",
]

logger = provide_logger(__name__)


class RootController(Controller):
    dependencies = {"event_repo": Provide(provide_event_repo), "agency_repo": Provide(provide_agency_repo)}

    @get("/", cache=120)
    async def root(
        self,
        event_repo: NamedDependency[EventRepository],
    ) -> Template:
        events = await event_repo.get_multiple_pretty_events_by_types(
            [
                EventType.GTFS_DATABASE_UPDATED,
                EventType.REALTIME_DATABASE_UPDATED,
                EventType.REALTIME_VEHICLES_DATABASE_UPDATED,
                EventType.STOP_FEATURES_DATABASE_UPDATED,
                EventType.RECORD_TS_STOP_TIMES,
            ]
        )

        gtfs_updated_event = events.get(EventType.GTFS_DATABASE_UPDATED)
        realtime_updated_event = events.get(EventType.REALTIME_DATABASE_UPDATED)
        vehicles_updated_event = events.get(EventType.REALTIME_VEHICLES_DATABASE_UPDATED)
        stop_features_updated_event = events.get(EventType.STOP_FEATURES_DATABASE_UPDATED)
        delays_recorded_event = events.get(EventType.RECORD_TS_STOP_TIMES)

        return Template(
            template_name="index.html",
            context={
                "gtfs_updated": gtfs_updated_event,
                "realtime_updated": realtime_updated_event,
                "vehicles_updated": vehicles_updated_event,
                "stop_features_updated": stop_features_updated_event,
                "delays_recorded": delays_recorded_event,
            },
        )

    @get("/about")
    async def about(self) -> Template:
        return Template(template_name="about.html")

    @get("/apidocs")
    async def api_docs(self) -> Template:
        return Template(template_name="api_docs.html")

    @get("/healthcheck")
    async def healthcheck(self) -> str:
        try:
            await test_database_connections()
        except Exception as e:
            logger.error("Database connection refused on healthcheck", exc_info=e)
            raise HTTPException(status_code=500) from e
        return "OK"

    @get("/exception")
    async def exception(self) -> Response:
        raise HTTPException(status_code=500, detail="Test exception")

    @get("/stops")
    async def stop(self) -> Template:
        return Template("gtfs_search/stop_search.html")

    @get("/routes")
    async def route(self) -> Template:
        return Template("gtfs_search/route_search.html")

    @get("/delays-explained")
    async def delays_explained(self) -> Template:
        return Template("delays/explained.html")

    @get("/maps")
    async def maps(self, agency_repo: NamedDependency[AgencyRepository]) -> Template:
        agencies = await agency_repo.get_many()
        all_agency = AgencyModel(id="All", name="All Agencies Combined")
        agencies.append(all_agency)
        return Template(
            "maps/index.html",
            context={"agencies": agencies, "map_types": StaticStopMapTypes},
        )

    @get("/stats")
    async def stats(self) -> Template:
        return Template(
            "stats/index.html",
            context={},
        )

    # Static files on the root / path
    @get("/favicon.ico")
    async def favicon(self) -> File:
        return File(
            path=f"{APP_DIR}/{STATIC_DIR}/favicon.ico",
            content_disposition_type="inline",
            media_type="image/vnd.microsoft.icon",
            filename="favicon.ico",
        )

    @get("/site.webmanifest")
    async def site_manifest(self) -> File:
        return File(
            path=f"{APP_DIR}/{STATIC_DIR}/site.webmanifest",
            content_disposition_type="inline",
            media_type="application/manifest+json",
            filename="site.webmanifest",
        )

    @get("/robots.txt")
    async def robots(self) -> File:
        return File(
            path=f"{APP_DIR}/{STATIC_DIR}/robots.txt",
            content_disposition_type="inline",
            media_type="text/plain",
            filename="robots.txt",
        )

    @get(
        "/.well-known/appspecific/com.chrome.devtools.json",
        include_in_schema=False,
    )
    async def chrome_devtools_well_known(self) -> dict[str, str]:
        """Chrome DevTools probes this URL; empty JSON avoids spurious 404/tracebacks in logs."""
        return {}

    @get("/favicon-16x16.png")
    async def favicon_16(self) -> File:
        return File(
            path=f"{APP_DIR}/{STATIC_DIR}/favicon-16x16.png",
            content_disposition_type="inline",
            media_type="image/png",
            filename="favicon-16x16.png",
        )

    @get("/favicon-32x32.png")
    async def favicon_32(self) -> File:
        return File(
            path=f"{APP_DIR}/{STATIC_DIR}/favicon-32x32.png",
            content_disposition_type="inline",
            media_type="image/png",
            filename="favicon-32x32.png",
        )

    @get("/apple-touch-icon.png")
    async def apple_touch(self) -> File:
        return File(
            path=f"{APP_DIR}/{STATIC_DIR}/apple-touch-icon.png",
            content_disposition_type="inline",
            media_type="image/png",
            filename="apple-touch-icon.png",
        )

    @get("/android-chrome-192x192.png")
    async def android_192(self) -> File:
        return File(
            path=f"{APP_DIR}/{STATIC_DIR}/android-chrome-192x192.png",
            content_disposition_type="inline",
            media_type="image/png",
            filename="android-chrome-192x192.png",
        )

    @get("/android-chrome-512x512.png")
    async def android_512(self) -> File:
        return File(
            path=f"{APP_DIR}/{STATIC_DIR}/android-chrome-512x512.png",
            content_disposition_type="inline",
            media_type="image/png",
            filename="android-chrome-512x512.png",
        )
