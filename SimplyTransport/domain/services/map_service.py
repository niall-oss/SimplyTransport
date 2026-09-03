from collections import defaultdict
from itertools import cycle
from typing import Literal

from advanced_alchemy.exceptions import NotFoundError
from litestar.di import NamedDependency
from SimplyTransport.api_contract.map_payloads import (
    AgencyRoutesMapPayload,
    GeoJSONLineString,
    NearbyMapPayload,
    RouteLayer,
    RouteMapPayload,
    StaticStopsMapPayload,
    StopMapPayload,
    StopMapStop,
    VehiclePoint,
)
from SimplyTransport.domain.maps.colors import Colors
from SimplyTransport.domain.realtime.vehicle.model import RTVehicleModel
from SimplyTransport.domain.shape.model import ShapeGeometryRow
from SimplyTransport.lib.cache import RedisService
from sqlalchemy.ext.asyncio import AsyncSession

from ...lib.logging.logging import provide_logger
from ...lib.tracing import CreateSpan
from ..maps.enums import StaticStopMapTypes
from ..realtime.vehicle.repo import RTVehicleRepository
from ..route.repo import RouteRepository
from ..shape.repo import ShapeRepository
from ..stop.model import StopModel
from ..stop.repo import StopRepository
from ..trip.repo import TripRepository

logger = provide_logger(__name__)


def _vehicle_point_from_rt(
    v: RTVehicleModel,
    route_id: str,
    color_hex: str,
) -> VehiclePoint:
    route = v.trip.route
    agency = route.agency
    return VehiclePoint(
        route_id=route_id,
        lat=v.lat,
        lon=v.lon,
        vehicle_id=v.vehicle_id,
        trip_id=v.trip_id,
        color=color_hex,
        route_short_name=route.short_name or "",
        agency_name=agency.name if agency is not None else "",
        time_of_update=v.time_of_update,
    )


class MapService:
    def __init__(
        self,
        stop_repository: StopRepository,
        route_repository: RouteRepository,
        shape_repository: ShapeRepository,
        trip_repository: TripRepository,
        rt_vehicle_repository: RTVehicleRepository,
    ):
        self.stop_repository = stop_repository
        self.route_repository = route_repository
        self.shape_repository = shape_repository
        self.trip_repository = trip_repository
        self.rt_vehicle_repository = rt_vehicle_repository

    @CreateSpan()
    async def build_stop_map_payload(self, stop_id: str) -> StopMapPayload | None:
        """Build JSON for the realtime stop map (MapLibre client)."""
        stop = await self.stop_repository.get(stop_id)
        direction = await self.stop_repository.get_direction_of_stop(stop_id)
        routes = await self.route_repository.get_routes_by_stop_id_with_agency(stop_id)

        if stop.lat is None or stop.lon is None:
            return None

        route_ids = [route.id for route in routes]
        trips = await self.trip_repository.get_first_trips_by_route_ids(route_ids, direction)
        trip_by_route_id = {t.route_id: t for t in trips}

        vehicles_on_routes = await self.rt_vehicle_repository.get_vehicles_on_routes(route_ids, direction)
        vehicles_dict: dict[str, list[RTVehicleModel]] = defaultdict(list)
        for vehicle in vehicles_on_routes:
            vehicles_dict[vehicle.trip.route_id].append(vehicle)

        shape_ids = list(dict.fromkeys(trip.shape_id for trip in trips))
        shapes = await self.shape_repository.get_sequence_sorted_shapes_by_shape_ids(shape_ids)
        shapes_dict: dict[str, list[ShapeGeometryRow]] = defaultdict(list)
        for shape in shapes:
            shapes_dict[shape.shape_id].append(shape)

        route_colors = cycle(list(Colors))
        route_layers: list[RouteLayer] = []
        route_color_by_id: dict[str, str] = {}

        for route in routes:
            trip = trip_by_route_id.get(route.id)
            if trip is None:
                continue
            trip_shapes = shapes_dict.get(trip.shape_id, [])
            if not trip_shapes:
                continue
            locations = [(s.lat, s.lon) for s in trip_shapes]
            if not locations:
                continue
            color_enum = next(route_colors)
            color_hex = color_enum.to_hex()
            route_color_by_id[route.id] = color_hex
            coordinates = [[s.lon, s.lat] for s in trip_shapes]
            route_layers.append(
                RouteLayer(
                    route_id=route.id,
                    short_name=route.short_name,
                    long_name=route.long_name,
                    color=color_hex,
                    line=GeoJSONLineString(coordinates=coordinates),
                )
            )

        vehicles_payload: list[VehiclePoint] = []
        for route_id, vehs in vehicles_dict.items():
            v_color = route_color_by_id.get(route_id, "#888888")
            for v in vehs:
                vehicles_payload.append(_vehicle_point_from_rt(v, route_id, v_color))

        other_stops_on_routes = await self.stop_repository.get_stops_by_route_ids(route_ids, direction)

        stops_out: list[StopMapStop] = [
            StopMapStop(
                stop_id=stop.id,
                code=stop.code,
                name=stop.name,
                lat=float(stop.lat),
                lon=float(stop.lon),
                is_focus=True,
            )
        ]

        seen: set[str] = {stop.id}
        for s in other_stops_on_routes:
            if s.id in seen:
                continue
            seen.add(s.id)
            if s.lat is None or s.lon is None:
                continue
            stops_out.append(
                StopMapStop(
                    stop_id=s.id,
                    code=s.code,
                    name=s.name,
                    lat=float(s.lat),
                    lon=float(s.lon),
                    is_focus=False,
                )
            )

        return StopMapPayload(
            center=(stop.lon, stop.lat),
            zoom=14,
            focus_stop_id=stop.id,
            direction=direction,
            routes=route_layers,
            vehicles=vehicles_payload,
            stops=stops_out,
        )

    @CreateSpan()
    async def build_route_map_payload(self, route_id: str, direction: int) -> RouteMapPayload:
        """Build JSON for the realtime single-route map (MapLibre client)."""
        route = await self.route_repository.get_by_id_with_agency(route_id)
        trip = await self.trip_repository.get_first_trip_by_route_id(route_id, direction)
        if trip is None:
            raise NotFoundError(f"No trip found for route {route_id} and direction {direction}")
        shapes = await self.shape_repository.get_sequence_sorted_shapes_by_shape_id(trip.shape_id)
        if len(shapes) == 0:
            raise NotFoundError(f"No shapes found for route {route_id} and direction {direction}")

        first = shapes[0]
        color_hex = Colors.BLUE.to_hex()

        coordinates = [[s.lon, s.lat] for s in shapes]
        route_layer = RouteLayer(
            route_id=route.id,
            short_name=route.short_name,
            long_name=route.long_name,
            color=color_hex,
            line=GeoJSONLineString(coordinates=coordinates),
        )

        vehicles_on_route = await self.rt_vehicle_repository.get_vehicles_on_routes([route_id], direction)
        vehicles_payload: list[VehiclePoint] = [
            _vehicle_point_from_rt(v, route_id, color_hex) for v in vehicles_on_route
        ]

        route_stops = await self.stop_repository.get_stops_by_route_id(route_id, direction)

        stops_out: list[StopMapStop] = []
        for s in route_stops:
            if s.lat is None or s.lon is None:
                continue
            stops_out.append(
                StopMapStop(
                    stop_id=s.id,
                    code=s.code,
                    name=s.name,
                    lat=float(s.lat),
                    lon=float(s.lon),
                    is_focus=False,
                )
            )

        return RouteMapPayload(
            center=(first.lon, first.lat),
            zoom=12,
            route_id=route.id,
            direction=direction,
            route=route_layer,
            vehicles=vehicles_payload,
            stops=stops_out,
        )

    @staticmethod
    def _default_map_center() -> tuple[float, float]:
        """Default Ireland-ish center as (longitude, latitude)."""
        return (-7.514413484752406, 53.44928237017178)

    @classmethod
    def _center_from_stops(cls, stops: list[StopModel]) -> tuple[float, float]:
        if not stops:
            return cls._default_map_center()
        lats = [float(s.lat) for s in stops if s.lat is not None]
        lons = [float(s.lon) for s in stops if s.lon is not None]
        if not lats:
            return cls._default_map_center()
        return (sum(lons) / len(lons), sum(lats) / len(lats))

    @classmethod
    def _center_from_route_layers(cls, layers: list[RouteLayer]) -> tuple[float, float]:
        if not layers:
            return cls._default_map_center()
        for layer in layers:
            coords = layer.line.coordinates
            if coords:
                mid = coords[len(coords) // 2]
                return (mid[0], mid[1])
        return cls._default_map_center()

    def _stop_to_map_stop(self, stop: StopModel, *, is_focus: bool) -> StopMapStop | None:
        if stop.lat is None or stop.lon is None:
            return None
        return StopMapStop(
            stop_id=stop.id,
            code=stop.code,
            name=stop.name,
            lat=float(stop.lat),
            lon=float(stop.lon),
            is_focus=is_focus,
        )

    @CreateSpan()
    async def build_nearby_map_payload(
        self, latitude: float, longitude: float, radius_meters: int = 1200
    ) -> NearbyMapPayload:
        """
        Stops within ``radius_meters`` of the user point for MapLibre / JSON clients.
        """
        rm = float(radius_meters)
        stops = await self.stop_repository.get_stops_near_location(latitude, longitude, int(radius_meters))

        stops_out: list[StopMapStop] = []
        for stop in stops:
            s = self._stop_to_map_stop(stop, is_focus=False)
            if s is not None:
                stops_out.append(s)

        return NearbyMapPayload(
            center=(longitude, latitude),
            zoom=15,
            user_lat=latitude,
            user_lon=longitude,
            radius_meters=rm,
            stops=stops_out,
        )

    @CreateSpan()
    async def build_agency_routes_map_payload(
        self, agency_id: str | Literal["All"]
    ) -> AgencyRoutesMapPayload:
        if agency_id == "All":
            routes = await self.route_repository.get_with_agencies()
        else:
            routes = await self.route_repository.get_with_agencies_by_agency_id(agency_id)
        if len(routes) == 0:
            raise ValueError(f"No routes found for agency {agency_id}")
        route_ids = [route.id for route in routes]

        trips = await self.trip_repository.get_first_trips_by_route_ids(route_ids)
        trip_by_route_id = {t.route_id: t for t in trips}

        shape_ids = list(dict.fromkeys(trip.shape_id for trip in trips))
        shapes = await self.shape_repository.get_sequence_sorted_shapes_by_shape_ids(shape_ids)
        shapes_dict: dict[str, list[ShapeGeometryRow]] = defaultdict(list)
        for shape in shapes:
            shapes_dict[shape.shape_id].append(shape)

        route_colors = cycle(list(Colors))
        route_layers: list[RouteLayer] = []

        for route in routes:
            trip = trip_by_route_id.get(route.id)
            if trip is None:
                continue
            trip_shapes = shapes_dict.get(trip.shape_id, [])
            if not trip_shapes:
                continue
            color_enum = next(route_colors)
            color_hex = color_enum.to_hex()
            coordinates = [[s.lon, s.lat] for s in trip_shapes]
            route_layers.append(
                RouteLayer(
                    route_id=route.id,
                    short_name=route.short_name,
                    long_name=route.long_name,
                    color=color_hex,
                    line=GeoJSONLineString(coordinates=coordinates),
                )
            )

        if not route_layers:
            raise ValueError(f"No route geometry could be built for agency {agency_id}")

        center = self._center_from_route_layers(route_layers)
        return AgencyRoutesMapPayload(
            center=center,
            zoom=7,
            agency_id=agency_id,
            routes=route_layers,
        )

    async def _get_stops_for_static_map_type(self, map_type: StaticStopMapTypes) -> list[StopModel]:
        match map_type:
            case StaticStopMapTypes.ALL_STOPS:
                return await self.stop_repository.get_all_with_stop_feature()
            case StaticStopMapTypes.REALTIME_DISPLAYS:
                return await self.stop_repository.get_stops_with_realtime_displays()
            case StaticStopMapTypes.SHELTERED_STOPS:
                return await self.stop_repository.get_stops_with_shelters()
            case StaticStopMapTypes.UNSURVEYED:
                return await self.stop_repository.get_stops_that_are_unsurveyed()
            case _:
                logger.error(f"Invalid map type {map_type}")
                return []

    @CreateSpan()
    async def build_static_stop_map_payload(self, map_type: StaticStopMapTypes) -> StaticStopsMapPayload:
        stops = await self._get_stops_for_static_map_type(map_type)

        stops_out: list[StopMapStop] = []
        for stop in stops:
            s = self._stop_to_map_stop(stop, is_focus=False)
            if s is not None:
                stops_out.append(s)

        center = self._center_from_stops(stops)
        return StaticStopsMapPayload(
            center=center,
            zoom=7,
            map_type=str(map_type.value),
            stops=stops_out,
        )


async def provide_map_service(
    db_session: NamedDependency[AsyncSession], redis_service: NamedDependency[RedisService]
) -> MapService:
    """
    Provides a map service instance.

    Args:
        db_session (AsyncSession): The database session.

    Returns:
        MapService: An instance of the MapService class.
    """
    return MapService(
        StopRepository(session=db_session),
        RouteRepository(session=db_session, cache=redis_service),
        ShapeRepository(session=db_session),
        TripRepository(session=db_session),
        RTVehicleRepository(session=db_session),
    )
