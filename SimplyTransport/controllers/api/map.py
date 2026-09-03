from typing import Annotated

from advanced_alchemy.exceptions import NotFoundError
from litestar import Controller, MediaType, Request, get
from litestar.di import NamedDependency, Provide
from litestar.exceptions import NotFoundException, ValidationException
from litestar.params import FromPath, QueryParameter

from SimplyTransport.api_contract.map_payloads import (
    AgencyRoutesMapPayload,
    NearbyMapPayload,
    RouteMapPayload,
    StaticStopsMapPayload,
    StopMapPayload,
)
from SimplyTransport.domain.maps.enums import StaticStopMapTypes
from SimplyTransport.domain.services.map_service import MapService, provide_map_service
from SimplyTransport.lib.cache_keys import CacheKeys, key_builder_from_path

__all__ = ["MapController"]

_MAP_JSON_STATIC_TTL_S = 86400
_MAP_JSON_VEHICLE_TTL_S = 120


def _nearby_map_cache_key_builder(request: Request) -> str:
    """Match QueryParameter default for radius_meters when the query omits it."""
    radius = request.query_params.get("radius_meters")
    if radius is None:
        radius = "1200"
    return CacheKeys.StopMaps.STOP_MAP_NEARBY_KEY_TEMPLATE.value.format(
        latitude=request.query_params.get("latitude"),
        longitude=request.query_params.get("longitude"),
        radius_meters=radius,
    )


class MapController(Controller):
    dependencies = {
        "map_service": Provide(provide_map_service),
    }

    @get(
        "/stop/nearby",
        media_type=MediaType.JSON,
        summary="Get map data for stops near a point",
        description=(
            "Returns nearby stops within a radius of a latitude/longitude. "
            "Optional radius_meters defaults to 1200 and must be between 1 and 1500."
        ),
        cache=_MAP_JSON_STATIC_TTL_S,
        cache_key_builder=_nearby_map_cache_key_builder,
    )
    async def nearby_map_data(
        self,
        map_service: NamedDependency[MapService],
        latitude: Annotated[float, QueryParameter(name="latitude", description="Latitude")],
        longitude: Annotated[float, QueryParameter(name="longitude", description="Longitude")],
        radius_meters: Annotated[
            int,
            QueryParameter(
                name="radius_meters",
                ge=1,
                le=1500,
                description="Search radius in meters (1–1500). Defaults to 1200.",
            ),
        ] = 1200,
    ) -> NearbyMapPayload:
        return await map_service.build_nearby_map_payload(latitude, longitude, radius_meters)

    @get(
        "/stop/aggregated/{map_type:str}",
        media_type=MediaType.JSON,
        summary="Get map data for a static stop map type",
        description="Static stop map category (see enum).",
        raises=[ValidationException],
        cache=_MAP_JSON_STATIC_TTL_S,
        cache_key_builder=key_builder_from_path(
            CacheKeys.StaticMaps.STATIC_MAP_STOP_KEY_TEMPLATE, "map_type"
        ),
    )
    async def static_stops_map_data(
        self, map_type: FromPath[StaticStopMapTypes], map_service: NamedDependency[MapService]
    ) -> StaticStopsMapPayload:
        return await map_service.build_static_stop_map_payload(map_type)

    @get(
        "/stop/{stop_id:str}",
        media_type=MediaType.JSON,
        summary="Get map data for a stop",
        description=("Returns GeoJSON-friendly route lines, stops, and vehicle positions for the stop map."),
        raises=[NotFoundException],
        cache=_MAP_JSON_VEHICLE_TTL_S,
        cache_key_builder=key_builder_from_path(CacheKeys.StopMaps.STOP_MAP_KEY_TEMPLATE, "stop_id"),
    )
    async def stop_map_data(
        self, stop_id: FromPath[str], map_service: NamedDependency[MapService]
    ) -> StopMapPayload:
        try:
            payload = await map_service.build_stop_map_payload(stop_id)
        except NotFoundError as e:
            raise NotFoundException(detail=f"Stop not found with id {stop_id}") from e

        if payload is None:
            raise NotFoundException(detail=f"Stop not found with id {stop_id}")

        return payload

    @get(
        "/route/{route_id:str}/{direction:int}",
        media_type=MediaType.JSON,
        summary="Get map data for a route",
        description="Returns GeoJSON-friendly route line, stops, and vehicle positions for the route map.",
        raises=[NotFoundException],
        cache=_MAP_JSON_VEHICLE_TTL_S,
        cache_key_builder=key_builder_from_path(
            CacheKeys.RouteMaps.ROUTE_MAP_KEY_TEMPLATE, "route_id", "direction"
        ),
    )
    async def route_map_data(
        self, route_id: FromPath[str], direction: FromPath[int], map_service: NamedDependency[MapService]
    ) -> RouteMapPayload:
        try:
            return await map_service.build_route_map_payload(route_id, direction)
        except NotFoundError as e:
            raise NotFoundException(
                detail=f"Route map not found for route {route_id} and direction {direction}"
            ) from e

    @get(
        "/route/agency/{agency_id:str}",
        media_type=MediaType.JSON,
        summary="Get map data for all routes of an agency",
        description=('Use agency_id "All" for every agency.'),
        raises=[NotFoundException],
        cache=_MAP_JSON_STATIC_TTL_S,
        cache_key_builder=key_builder_from_path(
            CacheKeys.StaticMaps.STATIC_MAP_AGENCY_ROUTE_KEY_TEMPLATE, "agency_id"
        ),
    )
    async def agency_routes_map_data(
        self, agency_id: FromPath[str], map_service: NamedDependency[MapService]
    ) -> AgencyRoutesMapPayload:
        try:
            return await map_service.build_agency_routes_map_payload(agency_id)
        except ValueError as e:
            raise NotFoundException(detail=str(e)) from e
