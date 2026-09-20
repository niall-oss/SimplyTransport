import json
from datetime import datetime
from enum import StrEnum
from unittest.mock import AsyncMock, Mock, call

import pytest
from SimplyTransport.lib.cache import (
    CacheKeys,
    RedisService,
    redis_factory,
    redis_service_cache_config_factory,
    redis_store_factory,
)


@pytest.fixture
def mock_redis() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def redis_service(mock_redis: AsyncMock) -> RedisService:
    service = RedisService()
    service.redis = mock_redis
    return service


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "keys, pattern, expected_calls",
    [
        (["key1", "key2"], CacheKeys.StopMaps.STOP_MAP_DELETE_KEY_TEMPLATE, 1),
        ([], CacheKeys.StopMaps.STOP_MAP_DELETE_KEY_TEMPLATE, 0),
        (["key1", "key2"], CacheKeys.Meta.ALL_KEYS, 1),
    ],
)
async def test_delete_keys_by_pattern(
    keys: list, pattern: StrEnum, expected_calls: int, redis_service: RedisService, mock_redis: AsyncMock
):
    # Arrange
    mock_redis.keys.return_value = keys

    # Act
    await redis_service.delete_keys_by_pattern(pattern)

    # Assert
    mock_redis.keys.assert_called_once_with(pattern.value)
    assert mock_redis.delete.call_count == expected_calls


@pytest.mark.asyncio
async def test_delete_keys_by_patterns_runs_each_pattern(redis_service: RedisService, mock_redis: AsyncMock):
    mock_redis.keys.side_effect = [["a"], ["b"], []]
    await redis_service.delete_keys_by_patterns(
        CacheKeys.StopMaps.STOP_MAP_DELETE_ALL_KEY_TEMPLATE,
        CacheKeys.RouteMaps.ROUTE_MAP_DELETE_ALL_KEY_TEMPLATE,
        CacheKeys.RealTime.REALTIME_TRIP_DELETE_ALL_KEY_TEMPLATE,
    )
    assert mock_redis.keys.await_count == 3
    assert mock_redis.delete.await_count == 2


@pytest.mark.asyncio
async def test_delete_keys_list(redis_service: RedisService, mock_redis: AsyncMock):
    # Arrange
    keys = ["key1", "key2"]

    # Act
    await redis_service.delete_keys(keys)

    # Assert
    mock_redis.delete.assert_called_once_with("key1", "key2")


@pytest.mark.asyncio
async def test_delete_keys_set(redis_service: RedisService, mock_redis: AsyncMock):
    # Arrange
    keys = {"key1", "key2"}

    # Act
    await redis_service.delete_keys(keys)

    # Assert
    assert mock_redis.delete.call_args.args[0] in {"key1", "key2"}
    assert mock_redis.delete.call_count == 1


@pytest.mark.asyncio
async def test_delete_key(redis_service: RedisService, mock_redis: AsyncMock):
    key = CacheKeys.StopMaps.STOP_MAP_KEY_TEMPLATE.value.format(stop_id="stop_id")
    await redis_service.delete_key(key)
    mock_redis.delete.assert_called_once_with(key)


@pytest.mark.asyncio
async def test_delete_all_keys(redis_service: RedisService, mock_redis: AsyncMock):
    mock_redis.keys.return_value = ["key1", "key2", "key3"]
    await redis_service.delete_all_keys()
    mock_redis.delete.assert_called_once_with("key1", "key2", "key3")


@pytest.mark.asyncio
async def test_delete_all_no_keys_present(redis_service: RedisService, mock_redis: AsyncMock):
    await redis_service.delete_all_keys()
    mock_redis.delete.assert_called_once_with()


@pytest.mark.asyncio
async def test_count_all_keys(redis_service: RedisService, mock_redis: AsyncMock):
    mock_redis.dbsize.return_value = 3
    count = await redis_service.count_all_keys()
    assert count == 3


@pytest.mark.asyncio
async def test_set(redis_service: RedisService, mock_redis: AsyncMock):
    key = CacheKeys.StopMaps.STOP_MAP_KEY_TEMPLATE.value.format(stop_id="stop_id")
    await redis_service.set(key, "value")
    mock_redis.set.assert_called_once_with(key, "value", ex=60)


@pytest.mark.asyncio
async def test_get(redis_service: RedisService, mock_redis: AsyncMock):
    mock_redis.get.return_value = "value"
    key = CacheKeys.StopMaps.STOP_MAP_KEY_TEMPLATE.value.format(stop_id="stop_id")
    value = await redis_service.get(key)
    assert value == "value"
    mock_redis.get.assert_called_once_with(key)


def test_redis_factory():
    redis = redis_factory()
    assert redis.connection_pool.connection_kwargs["host"] == "127.0.0.1"
    assert redis.connection_pool.connection_kwargs["port"] == 6379
    assert redis.connection_pool.connection_kwargs["db"] == 0


def test_redis_service_cache_config_factory():
    config = redis_service_cache_config_factory()
    assert config.default_expiration == 60


def test_redis_store_factory():
    redis_store = redis_store_factory("test_name")
    assert redis_store.namespace is not None and "test_name" in redis_store.namespace


@pytest.mark.asyncio
async def test_check_keys_exist(redis_service: RedisService, mock_redis: AsyncMock):
    # Arrange
    keys = ["key1", "key2", "key3"]
    pipeline_mock = Mock()
    pipeline_mock.execute = AsyncMock(return_value=[True, False, True])
    mock_redis.pipeline = Mock(return_value=pipeline_mock)

    # Act
    result = await redis_service.check_keys_exist(keys)

    # Assert
    assert result == {"key1": True, "key2": False, "key3": True}
    assert pipeline_mock.exists.call_count == 3
    pipeline_mock.exists.assert_has_calls([call("key1"), call("key2"), call("key3")])


@pytest.mark.asyncio
async def test_set_many_empty_keys_with_expiry(redis_service: RedisService, mock_redis: AsyncMock):
    # Arrange
    keys = ["key1", "key2", "key3"]
    pipeline_mock = Mock()
    pipeline_mock.execute = AsyncMock(return_value=[True, True, True])
    mock_redis.pipeline = Mock(return_value=pipeline_mock)
    expiry = 120
    batch_size = 2

    # Act
    await redis_service.set_many_empty_keys(keys, expiration=expiry, batch_size=batch_size)

    # Assert
    assert mock_redis.pipeline.call_count == 2
    pipeline_mock.set.assert_has_calls(
        [
            call("key1", value="", ex=expiry),
            call("key2", value="", ex=expiry),
            call("key3", value="", ex=expiry),
        ]
    )
    assert pipeline_mock.execute.call_count == 2


@pytest.mark.parametrize(
    "input_data, expected_output",
    [
        # Basic types
        ({"string": "test"}, '{"string": "test"}'),
        ({"number": 42}, '{"number": 42}'),
        ({"bool": True}, '{"bool": true}'),
        # Datetime
        ({"date": datetime(2024, 1, 1, 12, 0)}, '{"date": "2024-01-01T12:00:00"}'),
        # Mixed types
        (
            {"string": "test", "date": datetime(2024, 1, 1), "number": 42},
            '{"string": "test", "date": "2024-01-01T00:00:00", "number": 42}',
        ),
        # Nested structure
        (
            {"nested": {"date": datetime(2024, 1, 1), "value": "test"}},
            '{"nested": {"date": "2024-01-01T00:00:00", "value": "test"}}',
        ),
    ],
)
def test_serialize(input_data, expected_output, redis_service):
    result = redis_service.serialize(input_data)
    assert json.loads(result) == json.loads(expected_output)


@pytest.mark.parametrize(
    "input_string, expected_output",
    [
        # Basic types
        ('{"string": "test"}', {"string": "test"}),
        ('{"number": 42}', {"number": 42}),
        ('{"bool": true}', {"bool": True}),
        # Datetime string
        ('{"date": "2024-01-01T12:00:00"}', {"date": datetime(2024, 1, 1, 12, 0)}),
        # Mixed types
        (
            '{"string": "test", "date": "2024-01-01T00:00:00", "number": 42}',
            {"string": "test", "date": datetime(2024, 1, 1), "number": 42},
        ),
        # Nested structure
        (
            '{"nested": {"date": "2024-01-01T00:00:00", "value": "test"}}',
            {"nested": {"date": datetime(2024, 1, 1), "value": "test"}},
        ),
    ],
)
def test_deserialize(input_string, expected_output, redis_service):
    result = redis_service.deserialize(input_string)
    assert result == expected_output
