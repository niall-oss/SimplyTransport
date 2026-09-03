from datetime import date, datetime, time

import pytest
from litestar.exceptions import ValidationException
from SimplyTransport.domain.enums import DayOfWeek
from SimplyTransport.lib.time_date_conversions import (
    convert_29_hours_to_24_hours,
    convert_joined_date_to_date,
    next_date_for_day,
    return_time_difference,
    validate_time_range,
)


@pytest.mark.parametrize(
    "start_time, end_time, expected",
    [
        (time(10, 0, 0), time(12, 0, 0), 2),
        (time(10, 0, 0), time(10, 0, 0), 0),
        (time(10, 0, 0), time(22, 0, 0), 12),
        (time(10, 0, 0), time(8, 0, 0), 2),
        (time(23, 0, 0), time(0, 0, 0), 1),
        (time(23, 0, 0), time(1, 0, 0), 2),
        (time(23, 0, 0), time(2, 0, 0), 3),
        (time(23, 0, 0), time(3, 0, 0), 4),
        (time(23, 0, 0), time(4, 0, 0), 5),
    ],
)
def test_return_time_difference(start_time, end_time, expected):
    assert return_time_difference(start_time, end_time) == expected


@pytest.mark.parametrize(
    "date_str, expected_date",
    [
        ("20220101", datetime(2022, 1, 1).date()),
        ("20221231", datetime(2022, 12, 31).date()),
        ("20221015", datetime(2022, 10, 15).date()),
        ("20220909", datetime(2022, 9, 9).date()),
        ("20220808", datetime(2022, 8, 8).date()),
        ("20280707", datetime(2028, 7, 7).date()),
        ("20280606", datetime(2028, 6, 6).date()),
        ("20280505", datetime(2028, 5, 5).date()),
    ],
)
def test_convert_joined_date_to_date(date_str, expected_date):
    assert convert_joined_date_to_date(date_str) == expected_date


@pytest.mark.parametrize(
    "time_29, expected_time",
    [
        ("23:00:00", time(23, 0, 0)),
        ("23:12:12", time(23, 12, 12)),
        ("24:00:00", time(0, 0, 0)),
        ("24:12:12", time(0, 12, 12)),
        ("25:00:00", time(1, 0, 0)),
        ("26:00:00", time(2, 0, 0)),
        ("27:00:00", time(3, 0, 0)),
        ("28:00:00", time(4, 0, 0)),
        ("29:54:54", time(5, 54, 54)),
    ],
)
def test_convert_29_hours_to_24_hours(time_29, expected_time):
    assert convert_29_hours_to_24_hours(time_29) == expected_time


@pytest.mark.parametrize(
    "start_time, end_time",
    [
        (datetime(2023, 10, 10, 10, 0, 0), datetime(2023, 10, 10, 12, 0, 0)),
        (datetime(2023, 10, 10, 10, 0, 0), datetime(2023, 10, 10, 10, 0, 0)),
        (None, datetime(2023, 10, 10, 10, 0, 0)),
        (datetime(2023, 10, 10, 10, 0, 0), None),
        (None, None),
    ],
)
def test_validate_time_range_no_exception(start_time, end_time):
    try:
        validate_time_range(start_time, end_time)
    except ValidationException:
        pytest.fail("validate_time_range raised ValidationException unexpectedly!")


@pytest.mark.parametrize(
    "start_time, end_time",
    [
        (datetime(2023, 10, 10, 12, 0, 0), datetime(2023, 10, 10, 10, 0, 0)),
        (datetime(2023, 10, 10, 10, 0, 1), datetime(2023, 10, 10, 10, 0, 0)),
    ],
)
def test_validate_time_range_exception(start_time, end_time):
    with pytest.raises(ValidationException):
        validate_time_range(start_time, end_time)


def test_next_date_for_day_same_weekday():
    assert next_date_for_day(DayOfWeek.WEDNESDAY, from_date=date(2021, 6, 30)) == date(2021, 6, 30)


def test_next_date_for_day_later_in_week():
    assert next_date_for_day(DayOfWeek.SATURDAY, from_date=date(2021, 6, 30)) == date(2021, 7, 3)


def test_next_date_for_day_wraps_to_next_week():
    assert next_date_for_day(DayOfWeek.MONDAY, from_date=date(2021, 6, 30)) == date(2021, 7, 5)
