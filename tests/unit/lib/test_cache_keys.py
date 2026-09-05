from unittest.mock import AsyncMock, PropertyMock

from litestar import Request
from SimplyTransport.lib.cache_keys import (
    CacheKeys,
    key_builder_from_header,
    key_builder_from_path,
    key_builder_from_path_and_query,
    key_builder_from_query,
)


def test_key_builder_from_path():
    template = CacheKeys.StopMaps.STOP_MAP_KEY_TEMPLATE
    key_builder = key_builder_from_path(template, "stop_id")
    request = AsyncMock(spec=Request)
    type(request).path_params = PropertyMock(return_value={"stop_id": "123"})

    assert key_builder(request) == "stop_map:123"


def test_key_builder_stop_detailed():
    template = CacheKeys.StopApi.DETAILED_KEY_TEMPLATE
    key_builder = key_builder_from_path(template, "id")
    request = AsyncMock(spec=Request)
    type(request).path_params = PropertyMock(return_value={"id": "8240DB000324"})

    assert key_builder(request) == "stop_detailed:8240DB000324"


def test_key_builder_from_path_with_multiple_args():
    template = CacheKeys.Schedules.SCHEDULE_KEY_TEMPLATE
    key_builder = key_builder_from_path(template, "stop_id", "day")
    request = AsyncMock(spec=Request)
    type(request).path_params = PropertyMock(return_value={"stop_id": "123", "day": "1"})

    assert key_builder(request) == "schedule:123:1"


def test_key_builder_from_path_with_missing_args():
    template = CacheKeys.Schedules.SCHEDULE_KEY_TEMPLATE
    key_builder = key_builder_from_path(template, "stop_id", "day")
    request = AsyncMock(spec=Request)
    type(request).path_params = PropertyMock(return_value={"stop_id": "123"})

    assert key_builder(request) == "schedule:123:None"


def test_key_builder_from_query():
    template = CacheKeys.StopMaps.STOP_MAP_KEY_TEMPLATE
    key_builder = key_builder_from_query(template, "stop_id")
    request = AsyncMock(spec=Request)
    type(request).query_params = PropertyMock(return_value={"stop_id": "123"})

    assert key_builder(request) == "stop_map:123"


def test_key_builder_from_query_with_multiple_args():
    template = CacheKeys.Schedules.SCHEDULE_KEY_TEMPLATE
    key_builder = key_builder_from_query(template, "stop_id", "day")
    request = AsyncMock(spec=Request)
    type(request).query_params = PropertyMock(return_value={"stop_id": "123", "day": "1"})

    assert key_builder(request) == "schedule:123:1"


def test_key_builder_from_query_with_missing_args():
    template = CacheKeys.Schedules.SCHEDULE_KEY_TEMPLATE
    key_builder = key_builder_from_query(template, "stop_id", "day")
    request = AsyncMock(spec=Request)
    type(request).query_params = PropertyMock(return_value={"stop_id": "123"})

    assert key_builder(request) == "schedule:123:None"


def test_key_builder_from_query_nearby_map():
    template = CacheKeys.StopMaps.STOP_MAP_NEARBY_KEY_TEMPLATE
    key_builder = key_builder_from_query(template, "latitude", "longitude", "radius_meters")
    request = AsyncMock(spec=Request)
    type(request).query_params = PropertyMock(
        return_value={"latitude": "53.1", "longitude": "-7.2", "radius_meters": "800"}
    )

    assert key_builder(request) == "stop_map_nearby:53.1:-7.2:800"


def test_nearby_map_cache_key_builder_defaults_radius():
    from SimplyTransport.controllers.api.map_controller import _nearby_map_cache_key_builder

    request = AsyncMock(spec=Request)
    type(request).query_params = PropertyMock(return_value={"latitude": "53.1", "longitude": "-7.2"})

    assert _nearby_map_cache_key_builder(request) == "stop_map_nearby:53.1:-7.2:1200"


def test_key_builder_from_path_and_query():
    template = CacheKeys.Schedules.SCHEDULE_KEY_TEMPLATE
    key_builder = key_builder_from_path_and_query(template, path_args=["stop_id"], query_args=["day"])
    request = AsyncMock(spec=Request)
    type(request).path_params = PropertyMock(return_value={"stop_id": "123"})
    type(request).query_params = PropertyMock(return_value={"day": "1"})

    assert key_builder(request) == "schedule:123:1"


def test_key_builder_from_path_and_query_with_missing_args():
    template = CacheKeys.Schedules.SCHEDULE_KEY_TEMPLATE
    key_builder = key_builder_from_path_and_query(template, path_args=["stop_id"], query_args=["day"])
    request = AsyncMock(spec=Request)
    type(request).path_params = PropertyMock(return_value={"stop_id": "123"})
    type(request).query_params = PropertyMock(return_value={})

    assert key_builder(request) == "schedule:123:None"


def test_key_builder_from_header():
    template = CacheKeys.StopMaps.STOP_MAP_KEY_TEMPLATE
    key_builder = key_builder_from_header(template, "stop_id")
    request = AsyncMock(spec=Request)
    type(request).headers = PropertyMock(return_value={"stop_id": "123"})

    assert key_builder(request) == "stop_map:123"


def test_key_builder_from_header_with_missing_args():
    template = CacheKeys.StopMaps.STOP_MAP_KEY_TEMPLATE
    key_builder = key_builder_from_header(template, "stop_id")
    request = AsyncMock(spec=Request)
    type(request).headers = PropertyMock(return_value={})

    assert key_builder(request) == "stop_map:None"
