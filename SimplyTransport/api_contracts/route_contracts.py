from pydantic import Field
from SimplyTransport.api_contracts.base_contracts import ApiBaseModel
from SimplyTransport.api_contracts.enums import RouteTypeField


class Route(ApiBaseModel):
    id: str
    agency_id: str
    short_name: str
    long_name: str
    description: str | None
    route_type: RouteTypeField = Field(
        description="Type of transport on this route",
    )
    url: str | None
    color: str | None
    text_color: str | None
    dataset: str


class RouteWithTotal(ApiBaseModel):
    total: int
    routes: list[Route]
