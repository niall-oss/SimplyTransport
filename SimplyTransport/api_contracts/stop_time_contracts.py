from datetime import time

from SimplyTransport.api_contracts.base_contracts import ApiBaseModel
from SimplyTransport.domain.enums import DropoffType, PickupType, Timepoint


class StopTime(ApiBaseModel):
    id: int
    trip_id: str
    arrival_time: time
    departure_time: time
    stop_id: str
    stop_sequence: int
    stop_headsign: str | None
    pickup_type: PickupType | None
    dropoff_type: DropoffType | None
    timepoint: Timepoint | None
    dataset: str
