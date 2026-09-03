import json
from datetime import date, datetime, time, timedelta
from typing import Any

from litestar.exceptions import ValidationException
from SimplyTransport.domain.enums import DayOfWeek


def convert_29_hours_to_24_hours(time_str: str) -> time:
    """
    Converts a time string in 29-hour format to 24-hour format.
    Args:
        time_str (str): A string representing time in the format "HH:MM:SS",
                        where HH can be greater than 23.
    Returns:
        time: A time object representing the converted time in 24-hour format.
    """

    hours, minutes, seconds = map(int, time_str.split(":"))
    return time((hours - 24) if hours > 23 else hours, minutes, seconds)


def convert_joined_date_to_date(date: str) -> date:
    """
    Converts a date string in the format 'YYYYMMDD' to a date object.

    Args:
        date (str): The date string to convert, in the format 'YYYYMMDD'.

    Returns:
        date: A date object representing the given date string.
    """
    return datetime.strptime(date, "%Y%m%d").date()


class DateTimeEncoderForJson(json.JSONEncoder):
    def default(self, o: Any) -> str:
        if isinstance(o, datetime):
            return o.strftime("%H:%M:%S %d-%m-%Y")
        return super().default(o)


def return_time_difference(start_time: time, end_time: time) -> int:
    """
    Calculate the difference in hours between two time objects.
    Args:
        start_time (time): The starting time.
        end_time (time): The ending time.
    Returns:
        int: The difference in hours between the two times. If the times are the same, returns 0.
             The difference is always the smallest possible number of hours (0 to 12).
    """
    if start_time == end_time:
        return 0

    difference = (end_time.hour - start_time.hour) % 24
    if difference > 12:
        difference = 24 - difference

    return difference


def validate_time_range(start_time: datetime | None, end_time: datetime | None) -> None:
    """
    Validates that the start time is not greater than the end time.

    Args:
        start_time (datetime | None): The start time to validate.
        end_time (datetime | None): The end time to validate.

    Raises:
        ValidationException: If the start time is greater than the end time.
    """

    if start_time and end_time and start_time > end_time:
        raise ValidationException(
            detail=f"Start time cannot be greater than end time {start_time} > {end_time}"
        )


def next_date_for_day(day: DayOfWeek, from_date: date | None = None) -> date:
    """Return from_date if it is already `day`, otherwise the next matching weekday."""
    start = from_date or date.today()
    days_ahead = (int(day) - start.weekday()) % 7
    return start + timedelta(days=days_ahead)
