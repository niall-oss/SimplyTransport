from datetime import date

from pydantic import Field
from SimplyTransport.api_contracts.base_contracts import ApiBaseModel
from SimplyTransport.domain.enums import ExceptionType


class CalendarDate(ApiBaseModel):
    id: int
    service_id: str
    date: date
    exception_type: ExceptionType = Field(
        description="Determines whether the service is added or removed on the date",
        examples=["added", "removed"],
    )
    dataset: str


class CalendarDateWithTotal(ApiBaseModel):
    total: int
    calendar_dates: list[CalendarDate]
