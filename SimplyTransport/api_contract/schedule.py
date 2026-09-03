from SimplyTransport.api_contract.base import ApiBaseModel
from SimplyTransport.api_contract.route import Route
from SimplyTransport.api_contract.stop_time import StopTime
from SimplyTransport.api_contract.trip import Trip


class StaticSchedule(ApiBaseModel):
    route: Route
    stop_time: StopTime
    trip: Trip
    is_added_exception: bool
