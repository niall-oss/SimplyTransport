"""Assemble API contracts for detailed stop reads (routes + features)."""

from SimplyTransport.api_contracts.map_contracts import RouteSummary, StopFeatureSummary
from SimplyTransport.api_contracts.stop_contracts import Stop, StopDetailed

from ..route.route_repo import RouteRepo
from ..stop.stop_repo import StopRepo


def _street_view_url(lat: float | None, lon: float | None) -> str:
    if lat is None or lon is None:
        return ""
    return f"https://www.google.com/maps?layer=c&cbll={lat},{lon}&cbp=0,0,,,"


async def assemble_stop_detailed(
    stop_repo: StopRepo,
    route_repo: RouteRepo,
    stop_id: str,
) -> StopDetailed:
    stop = await stop_repo.get_by_id_with_stop_feature(stop_id)
    route_models = await route_repo.get_routes_by_stop_id(stop_id)
    routes = [
        RouteSummary(route_id=r.id, short_name=r.short_name, long_name=r.long_name) for r in route_models
    ]
    stop_features: StopFeatureSummary | None = None
    if stop.stop_feature is not None:
        sf = stop.stop_feature
        stop_features = StopFeatureSummary(
            wheelchair_accessible=sf.wheelchair_accessability,
            shelter_active=sf.shelter_active,
            rtpi_active=sf.rtpi_active,
        )
    return StopDetailed(
        stop=Stop.model_validate(stop),
        routes=routes,
        stop_features=stop_features,
        street_view_url=_street_view_url(
            float(stop.lat) if stop.lat is not None else None,
            float(stop.lon) if stop.lon is not None else None,
        ),
    )
