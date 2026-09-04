from datetime import time

import pytest
from SimplyTransport.lib.gtfs_importers import (
    SHAPE_CSV_FIELDS,
    STOP_TIME_CSV_FIELDS,
    TRIP_CSV_FIELDS,
    ClearStrategy,
    choose_clear_strategy,
    csv_column_indexes,
    optional_float,
    optional_int,
    records_with_ids,
    shape_record,
    stop_time_record,
    trip_record,
)


@pytest.mark.parametrize(
    ("other_dataset_exists", "table_name", "expected"),
    [
        (True, "stop_time", ClearStrategy.DELETE),
        (True, "trip", ClearStrategy.DELETE),
        (False, "stop_time", ClearStrategy.TRUNCATE),
        (False, "shape", ClearStrategy.TRUNCATE),
        (False, "agency", ClearStrategy.TRUNCATE),
        (False, "trip", ClearStrategy.TRUNCATE),
        (False, "route", ClearStrategy.TRUNCATE),
        (False, "stop", ClearStrategy.TRUNCATE_CASCADE),
        (False, "rt_trip", ClearStrategy.TRUNCATE),
        (False, "rt_stop_time", ClearStrategy.TRUNCATE),
        (False, "rt_vehicle", ClearStrategy.TRUNCATE),
        (True, "rt_trip", ClearStrategy.DELETE),
    ],
)
def test_choose_clear_strategy(other_dataset_exists, table_name, expected):
    assert choose_clear_strategy(other_dataset_exists=other_dataset_exists, table_name=table_name) == expected


def test_optional_int_and_float():
    assert optional_int("") is None
    assert optional_int("3") == 3
    assert optional_float("") is None
    assert optional_float("1.5") == 1.5


def test_csv_column_indexes_strips_bom_and_maps_names():
    header = ["\ufefftrip_id", "arrival_time", "extra"]
    indexes = csv_column_indexes(header, ("trip_id", "arrival_time"))
    assert indexes == {"trip_id": 0, "arrival_time": 1}


def test_csv_column_indexes_missing_column():
    with pytest.raises(ValueError, match="missing required column"):
        csv_column_indexes(["trip_id"], STOP_TIME_CSV_FIELDS)


def test_trip_record():
    header = list(TRIP_CSV_FIELDS)
    row = ["t1", "r1", "s1", "sh1", "Headsign", "Short", "1", "block-a"]
    col = csv_column_indexes(header, TRIP_CSV_FIELDS)
    assert trip_record(row, col, "TFI") == (
        "t1",
        "r1",
        "s1",
        "sh1",
        "Headsign",
        "Short",
        1,
        "block-a",
        "TFI",
    )


def test_stop_time_record_converts_times_and_empty_optionals():
    header = list(STOP_TIME_CSV_FIELDS)
    row = ["t1", "25:15:00", "5:30:00", "stop-1", "4", "via town", "", "", ""]
    col = csv_column_indexes(header, STOP_TIME_CSV_FIELDS)
    assert stop_time_record(row, col, "TFI") == (
        "t1",
        time(1, 15, 0),
        time(5, 30, 0),
        "stop-1",
        4,
        "via town",
        None,
        None,
        None,
        "TFI",
    )


def test_records_with_ids_prepends_contiguous_ids():
    assert records_with_ids([("a",), ("b",)], 10) == [(10, "a"), (11, "b")]


def test_shape_record_empty_distance():
    header = list(SHAPE_CSV_FIELDS)
    row = ["sh1", "53.3", "-6.2", "2", ""]
    col = csv_column_indexes(header, SHAPE_CSV_FIELDS)
    assert shape_record(row, col, "TFI") == ("sh1", 53.3, -6.2, 2, None, "TFI")
