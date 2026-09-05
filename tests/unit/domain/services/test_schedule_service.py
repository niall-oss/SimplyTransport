from datetime import date, time
from unittest.mock import AsyncMock

import pytest
from SimplyTransport.domain.calendar.calendar_model import CalendarModel
from SimplyTransport.domain.calendar_dates.calendar_date_model import CalendarDateModel
from SimplyTransport.domain.enums import DayOfWeek, ExceptionType
from SimplyTransport.domain.route.route_model import RouteModel
from SimplyTransport.domain.schedule.static_schedule_model import StaticScheduleModel
from SimplyTransport.domain.services.schedule_service import ScheduleService
from SimplyTransport.domain.stop.stop_model import StopModel
from SimplyTransport.domain.stop_times.stop_time_model import StopTimeModel
from SimplyTransport.domain.trip.trip_model import TripModel

ON_DATE = date(2021, 6, 30)  # Wednesday


def _calendar(**overrides: object) -> CalendarModel:
    values: dict[str, object] = {
        "id": "svc1",
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


def _schedule(calendar: CalendarModel, trip_id: str = "trip1", stop_sequence: int = 1) -> StaticScheduleModel:
    return StaticScheduleModel(
        route=RouteModel(
            id="r1",
            agency_id="a1",
            short_name="15",
            long_name="Test",
            route_type=3,
            dataset="test",
        ),
        stop_time=StopTimeModel(
            trip_id=trip_id,
            arrival_time=time(10, 0),
            departure_time=time(10, 0),
            stop_id="s1",
            stop_sequence=stop_sequence,
            dataset="test",
        ),
        calendar=calendar,
        stop=StopModel(id="s1", name="Stop", dataset="test"),
        trip=TripModel(
            id=trip_id,
            route_id="r1",
            service_id=calendar.id,
            direction=0,
            shape_id="shape1",
        ),
        is_added_exception=False,
    )


def _removed_exception(service_id: str, exception_date: date = ON_DATE) -> CalendarDateModel:
    return CalendarDateModel(
        service_id=service_id,
        date=exception_date,
        exception_type=ExceptionType.removed,
        dataset="test",
    )


def _added_exception(service_id: str, exception_date: date = ON_DATE) -> CalendarDateModel:
    return CalendarDateModel(
        service_id=service_id,
        date=exception_date,
        exception_type=ExceptionType.added,
        dataset="test",
    )


@pytest.mark.asyncio
async def test_get_schedule_on_stop_for_day_should_call_repository():
    # Arrange
    schedule_repo = AsyncMock()
    calendar_date_repo = AsyncMock()
    schedule_service = ScheduleService(
        schedule_repo=schedule_repo,
        calendar_date_repo=calendar_date_repo,
    )

    stop_id = "stop_id"
    day = DayOfWeek.MONDAY

    # Act
    await schedule_service.get_schedule_on_stop_for_day(stop_id=stop_id, day=day)

    # Assert
    schedule_repo.get_static_schedules.assert_called_once_with(stop_id=stop_id, day=day)


@pytest.mark.asyncio
async def test_get_schedule_on_stop_for_day_should_have_equal_static_schedules():
    # Arrange
    mock_schedule_data = [AsyncMock(), AsyncMock()]
    schedule_repo = AsyncMock()
    schedule_repo.get_static_schedules.return_value = mock_schedule_data
    calendar_date_repo = AsyncMock()
    schedule_service = ScheduleService(
        schedule_repo=schedule_repo,
        calendar_date_repo=calendar_date_repo,
    )

    stop_id = "stop_id"
    day = DayOfWeek.MONDAY

    # Act
    result = await schedule_service.get_schedule_on_stop_for_day(stop_id=stop_id, day=day)

    # Assert
    schedule_repo.get_static_schedules.assert_called_once_with(stop_id=stop_id, day=day)
    assert len(result) == len(mock_schedule_data)


@pytest.mark.asyncio
async def test_get_schedule_on_stop_for_day_between_times_should_call_repository():
    # Arrange
    schedule_repo = AsyncMock()
    calendar_date_repo = AsyncMock()
    schedule_service = ScheduleService(
        schedule_repo=schedule_repo,
        calendar_date_repo=calendar_date_repo,
    )

    stop_id = "stop_id"
    day = DayOfWeek.MONDAY
    start_time = time(hour=10, minute=0, second=0)
    end_time = time(hour=11, minute=0, second=0)

    # Act
    await schedule_service.get_schedule_on_stop_for_day_between_times(
        stop_id=stop_id, day=day, start_time=start_time, end_time=end_time
    )

    # Assert
    schedule_repo.get_static_schedules.assert_called_once_with(
        stop_id=stop_id, day=day, start_time=start_time, end_time=end_time
    )


@pytest.mark.asyncio
async def test_get_schedule_on_stop_for_day_between_times_should_have_equal_static_schedules():
    # Arrange
    mock_schedule_data = [AsyncMock(), AsyncMock()]
    schedule_repo = AsyncMock()
    schedule_repo.get_static_schedules.return_value = mock_schedule_data
    calendar_date_repo = AsyncMock()
    schedule_service = ScheduleService(
        schedule_repo=schedule_repo,
        calendar_date_repo=calendar_date_repo,
    )

    stop_id = "stop_id"
    day = DayOfWeek.MONDAY
    start_time = time(hour=10, minute=0, second=0)
    end_time = time(hour=11, minute=0, second=0)

    # Act
    result = await schedule_service.get_schedule_on_stop_for_day_between_times(
        stop_id=stop_id, day=day, start_time=start_time, end_time=end_time
    )

    # Assert
    schedule_repo.get_static_schedules.assert_called_once_with(
        stop_id=stop_id, day=day, start_time=start_time, end_time=end_time
    )
    assert len(result) == len(mock_schedule_data)


@pytest.mark.asyncio
async def test_apply_custom_23_00_sorting_should_return_sorted_list_reverse():
    # Arrange
    mock_schedule_data = [
        StaticScheduleModel(
            stop_time=StopTimeModel(arrival_time=time.fromisoformat("01:01:01")),
            route=AsyncMock(),
            calendar=AsyncMock(),
            stop=AsyncMock(),
            trip=AsyncMock(),
            is_added_exception=False,
        ),
        StaticScheduleModel(
            stop_time=StopTimeModel(arrival_time=time.fromisoformat("23:00:00")),
            route=AsyncMock(),
            calendar=AsyncMock(),
            stop=AsyncMock(),
            trip=AsyncMock(),
            is_added_exception=False,
        ),
    ]
    schedule_repo = AsyncMock()
    calendar_date_repo = AsyncMock()
    schedule_service = ScheduleService(
        schedule_repo=schedule_repo,
        calendar_date_repo=calendar_date_repo,
    )

    # Act
    result = await schedule_service.apply_custom_23_00_sorting(mock_schedule_data)

    # Assert
    assert len(result) == len(mock_schedule_data)
    assert result[0] == mock_schedule_data[1]
    assert result[1] == mock_schedule_data[0]


@pytest.mark.asyncio
async def test_apply_custom_23_00_sorting_should_return_sorted_list_no_change():
    # Arrange
    mock_schedule_data = [
        StaticScheduleModel(
            stop_time=StopTimeModel(arrival_time=time.fromisoformat("23:00:00")),
            route=AsyncMock(),
            calendar=AsyncMock(),
            stop=AsyncMock(),
            trip=AsyncMock(),
            is_added_exception=False,
        ),
        StaticScheduleModel(
            stop_time=StopTimeModel(arrival_time=time.fromisoformat("01:01:01")),
            route=AsyncMock(),
            calendar=AsyncMock(),
            stop=AsyncMock(),
            trip=AsyncMock(),
            is_added_exception=False,
        ),
    ]
    schedule_repo = AsyncMock()
    calendar_date_repo = AsyncMock()
    schedule_service = ScheduleService(
        schedule_repo=schedule_repo,
        calendar_date_repo=calendar_date_repo,
    )

    # Act
    result = await schedule_service.apply_custom_23_00_sorting(mock_schedule_data)

    # Assert
    assert len(result) == len(mock_schedule_data)
    assert result[0] == mock_schedule_data[0]
    assert result[1] == mock_schedule_data[1]


@pytest.mark.asyncio
async def test_apply_custom_23_00_sorting_should_return_sorted_list_no_change_normal_times():
    # Arrange
    mock_schedule_data = [
        StaticScheduleModel(
            stop_time=StopTimeModel(arrival_time=time.fromisoformat("21:00:00")),
            route=AsyncMock(),
            calendar=AsyncMock(),
            stop=AsyncMock(),
            trip=AsyncMock(),
            is_added_exception=False,
        ),
        StaticScheduleModel(
            stop_time=StopTimeModel(arrival_time=time.fromisoformat("21:01:01")),
            route=AsyncMock(),
            calendar=AsyncMock(),
            stop=AsyncMock(),
            trip=AsyncMock(),
            is_added_exception=False,
        ),
    ]
    schedule_repo = AsyncMock()
    calendar_date_repo = AsyncMock()
    schedule_service = ScheduleService(
        schedule_repo=schedule_repo,
        calendar_date_repo=calendar_date_repo,
    )

    # Act
    result = await schedule_service.apply_custom_23_00_sorting(mock_schedule_data)

    # Assert
    assert len(result) == len(mock_schedule_data)
    assert result[0] == mock_schedule_data[0]
    assert result[1] == mock_schedule_data[1]


@pytest.mark.asyncio
async def test_remove_exceptions_keeps_in_range_weekday_service():
    calendar_date_repo = AsyncMock()
    calendar_date_repo.get_removed_exceptions_on_date.return_value = []
    schedule_service = ScheduleService(AsyncMock(), calendar_date_repo)
    schedule = _schedule(_calendar())

    result = await schedule_service.remove_exceptions_and_inactive_calendars([schedule], on_date=ON_DATE)

    assert result == [schedule]
    calendar_date_repo.get_removed_exceptions_on_date.assert_called_once_with(date=ON_DATE)


@pytest.mark.asyncio
async def test_remove_exceptions_drops_outside_date_range():
    calendar_date_repo = AsyncMock()
    calendar_date_repo.get_removed_exceptions_on_date.return_value = []
    schedule_service = ScheduleService(AsyncMock(), calendar_date_repo)
    schedule = _schedule(_calendar(end_date=date(2021, 6, 1)))

    result = await schedule_service.remove_exceptions_and_inactive_calendars([schedule], on_date=ON_DATE)

    assert result == []


@pytest.mark.asyncio
async def test_remove_exceptions_drops_when_weekday_flag_is_off():
    calendar_date_repo = AsyncMock()
    calendar_date_repo.get_removed_exceptions_on_date.return_value = []
    schedule_service = ScheduleService(AsyncMock(), calendar_date_repo)
    schedule = _schedule(_calendar(wednesday=0))

    result = await schedule_service.remove_exceptions_and_inactive_calendars([schedule], on_date=ON_DATE)

    assert result == []


@pytest.mark.asyncio
async def test_remove_exceptions_drops_removed_service_on_date():
    calendar_date_repo = AsyncMock()
    calendar_date_repo.get_removed_exceptions_on_date.return_value = [_removed_exception("svc1")]
    schedule_service = ScheduleService(AsyncMock(), calendar_date_repo)
    schedule = _schedule(_calendar())

    result = await schedule_service.remove_exceptions_and_inactive_calendars([schedule], on_date=ON_DATE)

    assert result == []


@pytest.mark.asyncio
async def test_remove_exceptions_ignores_removed_exception_for_other_service():
    calendar_date_repo = AsyncMock()
    calendar_date_repo.get_removed_exceptions_on_date.return_value = [_removed_exception("other")]
    schedule_service = ScheduleService(AsyncMock(), calendar_date_repo)
    schedule = _schedule(_calendar())

    result = await schedule_service.remove_exceptions_and_inactive_calendars([schedule], on_date=ON_DATE)

    assert result == [schedule]


@pytest.mark.asyncio
async def test_add_in_added_exceptions_returns_unchanged_when_none():
    schedule_repo = AsyncMock()
    calendar_date_repo = AsyncMock()
    calendar_date_repo.get_added_exceptions_on_date.return_value = []
    schedule_service = ScheduleService(schedule_repo, calendar_date_repo)
    schedule = _schedule(_calendar())

    result = await schedule_service.add_in_added_exceptions([schedule], on_date=ON_DATE, stop_id="s1")

    assert result == [schedule]
    schedule_repo.get_static_schedules_for_service_ids.assert_not_called()


@pytest.mark.asyncio
async def test_add_in_added_exceptions_appends_and_flags_new_trips():
    extra = _schedule(_calendar(id="holiday", monday=0, tuesday=0, wednesday=0), trip_id="extra1")
    schedule_repo = AsyncMock()
    schedule_repo.get_static_schedules_for_service_ids.return_value = [extra]
    calendar_date_repo = AsyncMock()
    calendar_date_repo.get_added_exceptions_on_date.return_value = [_added_exception("holiday")]
    schedule_service = ScheduleService(schedule_repo, calendar_date_repo)
    existing = _schedule(_calendar())

    result = await schedule_service.add_in_added_exceptions(
        [existing], on_date=ON_DATE, stop_id="s1", start_time=time(9, 0), end_time=time(11, 0)
    )

    assert result == [existing, extra]
    assert existing.is_added_exception is False
    assert extra.is_added_exception is True
    schedule_repo.get_static_schedules_for_service_ids.assert_called_once_with(
        service_ids=["holiday"],
        stop_id="s1",
        start_time=time(9, 0),
        end_time=time(11, 0),
        trips=None,
    )


@pytest.mark.asyncio
async def test_add_in_added_exceptions_dedupes_existing_trips():
    existing = _schedule(_calendar(id="holiday"), trip_id="same-trip")
    duplicate = _schedule(_calendar(id="holiday"), trip_id="same-trip")
    schedule_repo = AsyncMock()
    schedule_repo.get_static_schedules_for_service_ids.return_value = [duplicate]
    calendar_date_repo = AsyncMock()
    calendar_date_repo.get_added_exceptions_on_date.return_value = [_added_exception("holiday")]
    schedule_service = ScheduleService(schedule_repo, calendar_date_repo)

    result = await schedule_service.add_in_added_exceptions([existing], on_date=ON_DATE, stop_id="s1")

    assert result == [existing]
    assert existing.is_added_exception is False


@pytest.mark.asyncio
async def test_add_in_added_exceptions_fetches_when_incoming_list_is_empty():
    extra = _schedule(_calendar(id="holiday"), trip_id="extra1")
    schedule_repo = AsyncMock()
    schedule_repo.get_static_schedules_for_service_ids.return_value = [extra]
    calendar_date_repo = AsyncMock()
    calendar_date_repo.get_added_exceptions_on_date.return_value = [_added_exception("holiday")]
    schedule_service = ScheduleService(schedule_repo, calendar_date_repo)

    result = await schedule_service.add_in_added_exceptions([], on_date=ON_DATE, stop_id="s1")

    assert result == [extra]
    assert extra.is_added_exception is True
    schedule_repo.get_static_schedules_for_service_ids.assert_called_once()


@pytest.mark.asyncio
async def test_get_by_trip_id_calls_repository():
    # Arrange
    schedule_repo = AsyncMock()
    calendar_date_repo = AsyncMock()
    schedule_service = ScheduleService(
        schedule_repo=schedule_repo,
        calendar_date_repo=calendar_date_repo,
    )
    trip_id = "trip_id"

    # Act
    await schedule_service.get_by_trip_id(trip_id=trip_id)

    # Assert
    schedule_repo.get_by_trip_id.assert_called_once_with(trip_id=trip_id)
