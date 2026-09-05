from datetime import date, datetime, time

from advanced_alchemy.exceptions import NotFoundError
from advanced_alchemy.filters import OnBeforeAfter
from litestar import Controller, get
from litestar.di import NamedDependency, Provide
from litestar.exceptions import NotFoundException
from litestar.params import FromPath
from SimplyTransport.api_contracts.calendar_contracts import Calendar, CalendarWithTotal

from ...domain.calendar.calendar_repo import CalendarRepo, provide_calendar_repo

__all__ = ["CalendarController"]


class CalendarController(Controller):
    dependencies = {"repo": Provide(provide_calendar_repo)}

    @get("/", summary="All calendars")
    async def get_all_calendars(self, repo: NamedDependency[CalendarRepo]) -> list[Calendar]:
        result = await repo.get_many()
        return [Calendar.model_validate(obj) for obj in result]

    @get("/count", summary="All calendars with total count")
    async def get_all_calendars_and_count(self, repo: NamedDependency[CalendarRepo]) -> CalendarWithTotal:
        result, total = await repo.get_many_and_count()
        return CalendarWithTotal(total=total, calendars=[Calendar.model_validate(obj) for obj in result])

    @get("/{id:str}", summary="Calendar by service ID", raises=[NotFoundException])
    async def get_calendar_by_id(self, repo: NamedDependency[CalendarRepo], id: FromPath[str]) -> Calendar:
        try:
            result = await repo.get(id)
        except NotFoundError as e:
            raise NotFoundException(detail=f"Calendar not found with id {id}") from e
        return Calendar.model_validate(result)

    @get(
        "/date/{date:date}",
        summary="All active calendars on a given date",
        description="Date format = YYYY-MM-DD",
    )
    async def get_active_calendars_on_date(
        self, repo: NamedDependency[CalendarRepo], date: FromPath[date]
    ) -> list[Calendar]:
        start_date = datetime.combine(date, time.min)
        end_date = datetime.combine(date, time.max)

        result = await repo.get_many(
            OnBeforeAfter(field_name="start_date", on_or_before=start_date, on_or_after=None),
            OnBeforeAfter(field_name="end_date", on_or_before=None, on_or_after=end_date),
        )
        return [Calendar.model_validate(obj) for obj in result]
