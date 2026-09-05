"""Pydantic models for JSON map payloads (MapLibre / API)."""

from datetime import datetime
from typing import Literal

from pydantic import Field
from SimplyTransport.api_contracts.base_contracts import ApiBaseModel


class RouteSummary(ApiBaseModel):
    route_id: str
    short_name: str
    long_name: str


class GeoJSONLineString(ApiBaseModel):
    type: Literal["LineString"] = "LineString"
    coordinates: list[list[float]] = Field(
        ...,
        description="GeoJSON positions [longitude, latitude] per point",
    )


class RouteLayer(ApiBaseModel):
    route_id: str
    short_name: str
    long_name: str
    color: str
    line: GeoJSONLineString


class VehiclePoint(ApiBaseModel):
    route_id: str
    lat: float
    lon: float
    vehicle_id: int
    trip_id: str
    color: str
    route_short_name: str
    agency_name: str
    time_of_update: datetime


class StopFeatureSummary(ApiBaseModel):
    wheelchair_accessible: bool | None = None
    shelter_active: bool | None = None
    rtpi_active: bool | None = None


class StopMapStop(ApiBaseModel):
    stop_id: str
    code: str | None
    name: str
    lat: float
    lon: float
    is_focus: bool


class StopMapPayload(ApiBaseModel):
    center: tuple[float, float] = Field(
        ...,
        description="Map center as (longitude, latitude) for MapLibre",
    )
    zoom: int = 14
    focus_stop_id: str
    direction: int
    routes: list[RouteLayer]
    vehicles: list[VehiclePoint]
    stops: list[StopMapStop]


class RouteMapPayload(ApiBaseModel):
    """Single-route view (realtime route page) for MapLibre clients."""

    center: tuple[float, float] = Field(
        ...,
        description="Map center as (longitude, latitude) for MapLibre",
    )
    zoom: int = 12
    route_id: str
    direction: int
    route: RouteLayer
    vehicles: list[VehiclePoint]
    stops: list[StopMapStop]


class NearbyMapPayload(ApiBaseModel):
    """Map around a user point with nearby stops (search / geolocation)."""

    center: tuple[float, float] = Field(
        ...,
        description="Map center as (longitude, latitude) for MapLibre",
    )
    zoom: int = 15
    user_lat: float
    user_lon: float
    radius_meters: float
    stops: list[StopMapStop]


class AgencyRoutesMapPayload(ApiBaseModel):
    """All routes for one agency (or every agency) as separate colored layers."""

    center: tuple[float, float] = Field(
        ...,
        description="Map center as (longitude, latitude) for MapLibre",
    )
    zoom: int = 7
    agency_id: str
    routes: list[RouteLayer]


class StaticStopsMapPayload(ApiBaseModel):
    """Many stops for a static map type (sheltered, all stops, etc.)."""

    center: tuple[float, float] = Field(
        ...,
        description="Map center as (longitude, latitude) for MapLibre",
    )
    zoom: int = 7
    map_type: str
    stops: list[StopMapStop]
