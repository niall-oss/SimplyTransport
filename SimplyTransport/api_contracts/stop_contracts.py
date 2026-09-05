from pydantic import Field
from SimplyTransport.api_contracts.base_contracts import ApiBaseModel
from SimplyTransport.api_contracts.map_contracts import RouteSummary, StopFeatureSummary
from SimplyTransport.domain.enums import LocationType


class Stop(ApiBaseModel):
    id: str
    code: str | None
    name: str
    description: str | None
    lat: float | None
    lon: float | None
    zone_id: str | None
    url: str | None
    location_type: LocationType | None = Field(
        description="Indicates the type of the location",
    )
    parent_station: str | None
    dataset: str


class StopDetailed(ApiBaseModel):
    stop: Stop
    routes: list[RouteSummary]
    stop_features: StopFeatureSummary | None = None
    street_view_url: str = Field(
        default="",
        description="Google Street View link when lat/lon are present; empty otherwise.",
    )
