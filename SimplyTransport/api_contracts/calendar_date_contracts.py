from datetime import date

from pydantic import Field
from SimplyTransport.api_contracts.base_contracts import ApiBaseModel
from SimplyTransport.api_contracts.enums import ExceptionTypeField


class CalendarDate(ApiBaseModel):
    id: int
    service_id: str
    date: date
    exception_type: ExceptionTypeField = Field(
        description="Whether service is added or removed on this date",
    )
    dataset: str


class CalendarDateWithTotal(ApiBaseModel):
    total: int
    calendar_dates: list[CalendarDate]
