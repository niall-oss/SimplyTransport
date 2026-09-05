from pydantic import Field
from SimplyTransport.api_contracts.base_contracts import ApiBaseModel
from SimplyTransport.domain.enums import Direction


class Trip(ApiBaseModel):
    id: str
    route_id: str
    service_id: str
    shape_id: str
    headsign: str | None
    short_name: str | None
    direction: Direction = Field(description="Direction of travel. Mapping between agencies could differ.")
    block_id: str | None
    dataset: str


class TripsWithTotal(ApiBaseModel):
    total: int
    trips: list[Trip]
