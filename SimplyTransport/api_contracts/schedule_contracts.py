from SimplyTransport.api_contracts.base_contracts import ApiBaseModel
from SimplyTransport.api_contracts.route_contracts import Route
from SimplyTransport.api_contracts.stop_time_contracts import StopTime
from SimplyTransport.api_contracts.trip_contracts import Trip


class StaticSchedule(ApiBaseModel):
    route: Route
    stop_time: StopTime
    trip: Trip
    is_added_exception: bool
