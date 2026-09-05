from datetime import date, datetime, time

from advanced_alchemy.filters import OnBeforeAfter
from litestar import Controller, get
from litestar.di import NamedDependency, Provide
from litestar.exceptions import NotFoundException
from litestar.params import FromPath
from SimplyTransport.api_contracts.calendar_date_contracts import CalendarDate, CalendarDateWithTotal

from ...domain.calendar_dates.calendar_date_repo import (
    CalendarDateRepo,
    provide_calendar_date_repo,
)

__all__ = ["CalendarDateController"]


class CalendarDateController(Controller):
    dependencies = {"repo": Provide(provide_calendar_date_repo)}

    @get("/", summary="All calendar dates")
    async def get_all_calendars(self, repo: NamedDependency[CalendarDateRepo]) -> list[CalendarDate]:
        result = await repo.get_many()
        return [CalendarDate.model_validate(obj) for obj in result]

    @get("/count", summary="All calendar dates with total count")
    async def get_all_calendars_and_count(
        self, repo: NamedDependency[CalendarDateRepo]
    ) -> CalendarDateWithTotal:
        result, total = await repo.get_many_and_count()
        return CalendarDateWithTotal(
            total=total, calendar_dates=[CalendarDate.model_validate(obj) for obj in result]
        )

    @get("/{service_id:str}", summary="CalendarDates by service ID", raises=[NotFoundException])
    async def get_calendar_dates_by_id(
        self, repo: NamedDependency[CalendarDateRepo], service_id: FromPath[str]
    ) -> list[CalendarDate]:
        result = await repo.get_many(service_id=service_id)
        if result is None or len(result) == 0:
            raise NotFoundException(detail=f"CalendarDates not found with service_id {service_id}")
        return [CalendarDate.model_validate(obj) for obj in result]

    @get(
        "/date/{date:date}",
        summary="All calendar dates on a given date",
        description="Date format = YYYY-MM-DD",
    )
    async def get_active_calendar_dates_on_date(
        self, repo: NamedDependency[CalendarDateRepo], date: FromPath[date]
    ) -> list[CalendarDate]:
        start_date = datetime.combine(date, time.min)
        end_date = datetime.combine(date, time.max)

        result = await repo.get_many(
            OnBeforeAfter(
                field_name="date",
                on_or_before=end_date,
                on_or_after=start_date,
            ),
        )
        return [CalendarDate.model_validate(obj) for obj in result]
