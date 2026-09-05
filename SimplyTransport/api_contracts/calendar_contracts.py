from datetime import date

from SimplyTransport.api_contracts.base_contracts import ApiBaseModel


class Calendar(ApiBaseModel):
    id: str
    monday: int
    tuesday: int
    wednesday: int
    thursday: int
    friday: int
    saturday: int
    sunday: int
    start_date: date
    end_date: date
    dataset: str


class CalendarWithTotal(ApiBaseModel):
    total: int
    calendars: list[Calendar]
