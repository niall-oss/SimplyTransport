from pydantic import Field
from SimplyTransport.api_contracts.base_contracts import ApiBaseModel
from SimplyTransport.api_contracts.enums import DirectionField


class Trip(ApiBaseModel):
    id: str
    route_id: str
    service_id: str
    shape_id: str
    headsign: str | None
    short_name: str | None
    direction: DirectionField = Field(
        description="Direction of travel. Agencies do not always use OUTBOUND and INBOUND the same way.",
    )
    block_id: str | None
    dataset: str


class TripsWithTotal(ApiBaseModel):
    total: int
    trips: list[Trip]
