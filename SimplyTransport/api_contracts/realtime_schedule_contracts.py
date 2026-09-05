from datetime import time

from SimplyTransport.api_contracts.base_contracts import ApiBaseModel
from SimplyTransport.domain.realtime.enums import OnTimeStatus
from SimplyTransport.domain.realtime.stop_time.rt_stop_time_model import RTStopTime
from SimplyTransport.domain.realtime.trip.rt_trip_model import RTTrip


class RealtimeSchedule(ApiBaseModel):
    rt_stop_time: RTStopTime | None
    rt_trip: RTTrip | None
    delay: str
    delay_in_seconds: int
    real_arrival_time: time
    real_eta_text: str
    on_time_status: OnTimeStatus
    is_trip_removed: bool
