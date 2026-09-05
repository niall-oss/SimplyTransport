from typing import cast
from unittest.mock import MagicMock

from SimplyTransport.domain.database_statistics.database_statistic_model import (
    DatabaseStatisticModel,
    DatabaseStatisticWithPercentage,
)
from SimplyTransport.domain.services.statistics_service import StatisticsService


def _svc() -> StatisticsService:
    return StatisticsService(database_statistic_repo=MagicMock(), ts_stop_time_repo=MagicMock())


def _stat(key: str, value: int) -> DatabaseStatisticModel:
    return cast(DatabaseStatisticModel, MagicMock(key=key, value=value))


def test_convert_stats_adds_totals_row_and_percentages():
    svc = _svc()
    stats = [
        _stat("agencies", 25),
        _stat("stops", 75),
    ]
    rows = svc.convert_stats_to_stats_with_percentage_totals(stats)
    assert rows[0].key == "Total Rows"
    assert rows[0].value == 100
    assert rows[0].percentage == 100
    assert rows[1].percentage == 25
    assert rows[2].percentage == 75


def test_convert_stats_uses_total_override():
    svc = _svc()
    stats = [_stat("a", 10)]
    rows = svc.convert_stats_to_stats_with_percentage_totals(
        stats, add_totals_row=False, total_override=50, decimals_places_to_round=1
    )
    assert len(rows) == 1
    assert rows[0].percentage == 20.0


def test_convert_stats_zero_total_does_not_divide():
    svc = _svc()
    stats = [_stat("empty", 0)]
    rows = svc.convert_stats_to_stats_with_percentage_totals(stats, total_override=0)
    assert rows[0].percentage == 0
    assert rows[1].percentage == 0
    assert rows[1].value == 0


def test_convert_stats_empty_list_with_totals_only():
    svc = _svc()
    rows = svc.convert_stats_to_stats_with_percentage_totals([])
    assert rows == [("Total Rows", 0, 0)]


def test_sort_stats_by_value():
    svc = _svc()
    rows = [
        DatabaseStatisticWithPercentage(key="a", value=1, percentage=10),
        DatabaseStatisticWithPercentage(key="b", value=5, percentage=50),
    ]
    sorted_rows = svc.sort_stats_by_value(rows)
    assert [row.key for row in sorted_rows] == ["b", "a"]
    assert [row.key for row in svc.sort_stats_by_value(rows, descending=False)] == ["a", "b"]
