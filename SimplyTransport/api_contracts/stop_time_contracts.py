from datetime import time

from pydantic import Field
from SimplyTransport.api_contracts.base_contracts import ApiBaseModel
from SimplyTransport.api_contracts.enums import DropoffTypeField, PickupTypeField, TimepointField


class StopTime(ApiBaseModel):
    id: int
    trip_id: str
    arrival_time: time
    departure_time: time
    stop_id: str
    stop_sequence: int
    stop_headsign: str | None
    pickup_type: PickupTypeField = Field(
        default=None,
        description="How riders board at this stop",
    )
    dropoff_type: DropoffTypeField = Field(
        default=None,
        description="How riders alight at this stop",
    )
    timepoint: TimepointField = Field(
        default=None,
        description="Whether times are exact. Null means exact.",
    )
    dataset: str
