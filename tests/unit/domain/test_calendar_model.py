from datetime import date

from SimplyTransport.domain.calendar.calendar_model import CalendarModel


def _all_days_calendar(**overrides: object) -> CalendarModel:
    values: dict[str, object] = {
        "id": "1",
        "monday": 1,
        "tuesday": 1,
        "wednesday": 1,
        "thursday": 1,
        "friday": 1,
        "saturday": 1,
        "sunday": 1,
        "start_date": date(2021, 1, 1),
        "end_date": date(2021, 12, 31),
        "dataset": "test",
    }
    values.update(overrides)
    return CalendarModel(**values)  # type: ignore[arg-type]


def test_calendar_model_is_active_on_date_in_range():
    calendar = _all_days_calendar()
    assert calendar.is_active_on_date(date(2021, 1, 1)) is True
    assert calendar.is_active_on_date(date(2021, 12, 31)) is True
    assert calendar.is_active_on_date(date(2021, 6, 30)) is True
    assert calendar.is_active_on_date(date(2020, 1, 2)) is False
    assert calendar.is_active_on_date(date(2022, 1, 2)) is False


def test_calendar_model_is_active_on_date_requires_weekday_flag():
    calendar = _all_days_calendar(saturday=0, sunday=0)
    assert calendar.is_active_on_date(date(2021, 6, 30)) is True  # Wednesday
    assert calendar.is_active_on_date(date(2021, 7, 3)) is False  # Saturday
    assert calendar.is_active_on_date(date(2021, 7, 4)) is False  # Sunday
