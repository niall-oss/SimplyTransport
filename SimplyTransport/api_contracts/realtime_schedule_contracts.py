from datetime import date, time

from pydantic import Field
from SimplyTransport.api_contracts.base_contracts import ApiBaseModel
from SimplyTransport.api_contracts.enums import DirectionField
from SimplyTransport.domain.realtime.enums import OnTimeStatus, ScheduleRelationship


class RTStopTime(ApiBaseModel):
    stop_id: str
    trip_id: str
    stop_sequence: int
    schedule_relationship: ScheduleRelationship
    arrival_delay: int
    departure_delay: int


class RTTrip(ApiBaseModel):
    trip_id: str
    route_id: str
    start_time: time
    start_date: date
    schedule_relationship: ScheduleRelationship
    direction: DirectionField = Field(
        description="Direction of travel. Agencies do not always use OUTBOUND and INBOUND the same way.",
    )


class RealtimeSchedule(ApiBaseModel):
    rt_stop_time: RTStopTime | None
    rt_trip: RTTrip | None
    delay: str
    delay_in_seconds: int
    real_arrival_time: time
    real_eta_text: str
    on_time_status: OnTimeStatus
    is_trip_removed: bool
