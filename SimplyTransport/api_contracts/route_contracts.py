from pydantic import Field
from SimplyTransport.api_contracts.base_contracts import ApiBaseModel
from SimplyTransport.domain.enums import RouteType


class Route(ApiBaseModel):
    id: str
    agency_id: str
    short_name: str
    long_name: str
    description: str | None
    route_type: RouteType = Field(
        description="Indicates the type of transportation used on a route",
    )
    url: str | None
    color: str | None
    text_color: str | None
    dataset: str


class RouteWithTotal(ApiBaseModel):
    total: int
    routes: list[Route]
