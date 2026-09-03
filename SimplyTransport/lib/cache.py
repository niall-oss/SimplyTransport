from __future__ import annotations

import json
from collections.abc import Iterable, Sequence
from datetime import datetime
from enum import StrEnum
from typing import Any

from litestar.config.response_cache import ResponseCacheConfig
from litestar.stores.redis import RedisStore
from opentelemetry.instrumentation.redis import RedisInstrumentor
from redis.asyncio import Redis
from SimplyTransport.lib.extensions.chunking import chunk_list

from . import settings
from .cache_keys import CacheKeys

RedisInstrumentor().instrument()


def redis_factory() -> Redis:
    """
    Creates and returns a Redis instance.

    Returns:
        Redis: The Redis instance.
    """
    # If no password is set, attempt to connect to an un-authenticated redis instance
    if not settings.app.REDIS_PASSWORD:
        return Redis(
            host=settings.app.REDIS_HOST,
            port=settings.app.REDIS_PORT,
            db=0,
        )

    return Redis(
        host=settings.app.REDIS_HOST,
        port=settings.app.REDIS_PORT,
        db=0,
        password=settings.app.REDIS_PASSWORD,
    )


def redis_store_factory(name: str) -> RedisStore:
    """
    Factory function that creates and returns a RedisStore object.

    Litestar's response cache uses store name ``response_cache``. Namespacing that store
    with ``VERSION`` busts cached HTML after a deploy version bump (cached bodies embed
    old asset query strings).

    Returns:
        RedisStore: The created RedisStore object.
    """
    namespace = f"{settings.app.NAME}:{name}"
    if name == "response_cache":
        namespace = f"{settings.app.NAME}:{name}:v{settings.app.VERSION}"
    return RedisStore(redis_factory(), namespace=namespace)


def redis_service_cache_config_factory() -> ResponseCacheConfig:
    """
    Factory function that returns a ResponseCacheConfig object for Redis service cache.
    If a store exists in the registry, it will be used to create the
    cache configuration which should only be redis.

    Returns:
        ResponseCacheConfig: The cache configuration object.
    """
    return ResponseCacheConfig(default_expiration=60)


class RedisService:
    def __init__(self, default_expiration: int = 60) -> None:
        self.redis = redis_factory()
        self.default_expiration = default_expiration

    async def __aenter__(self) -> RedisService:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.redis.aclose()

    async def delete_keys_by_pattern(self, pattern: StrEnum) -> None:
        """
        Delete keys from the cache based on the given pattern.

        Args:
            pattern (StrEnum): The pattern to match the keys.

        Returns:
            None
        """
        keys = await self.redis.keys(pattern.value)
        if keys:
            await self.redis.delete(*keys)

    async def delete_key(self, key: str) -> None:
        """
        Delete a key from the cache.

        Args:
            key (StrEnum): The key to delete from the cache.

        Returns:
            None
        """
        await self.redis.delete(key)

    async def delete_keys(self, keys: Iterable[str]) -> None:
        """
        Delete keys from the cache.

        Args:
            keys (Iterable[str]): The keys to delete from the cache.

        Returns:
            None
        """
        await self.redis.delete(*keys)

    async def delete_all_keys(self) -> None:
        """
        Deletes all keys from the cache.
        """
        await self.delete_keys_by_pattern(CacheKeys.Meta.ALL_KEYS)

    async def count_all_keys(self) -> int:
        """
        Counts all keys in the cache.

        Returns:
            int: The number of keys in the cache.
        """
        return await self.redis.dbsize()

    async def set(self, key: str, value: str, expiration: int | None = None) -> None:
        """
        Set a value in the cache.

        Args:
            key (str): The key to set the value in the cache.
            value (str): The value to be stored in the cache.
            expiration (int, optional): The expiration time in seconds. Defaults to None.
        """
        await self.redis.set(key, value, ex=expiration or self.default_expiration)

    async def get(self, key: str) -> str | None:
        """
        Get a value from the cache.

        Args:
            key (str): The key to get the value from the cache.

        Returns:
            str | None: The value from the cache or None if the key does not exist.
        """
        return await self.redis.get(key)

    async def check_keys_exist(self, keys: Sequence[str]) -> dict[str, bool]:
        """
        Efficiently check if multiple keys exist using pipeline.

        Args:
            keys (Sequence[str]): Keys to check

        Returns:
            dict[str, bool]: Mapping of key to existence boolean.
                            True if key exists, False if it doesn't.
        """
        pipe = self.redis.pipeline()
        for key in keys:
            pipe.exists(key)

        results = await pipe.execute()
        return dict(zip(keys, (bool(result) for result in results), strict=True))

    async def set_many_empty_keys(
        self, keys: Sequence[str], expiration: int | None = None, batch_size: int = 1000
    ) -> None:
        """
        Efficiently set empty values for multiple keys with expiration using pipeline.

        Args:
            keys (Sequence[str]): Sequence of keys
            expiration (int): Seconds until key expires
        """
        for batch in chunk_list(keys, batch_size):
            pipe = self.redis.pipeline()
            for key in batch:
                pipe.set(key, value="", ex=expiration or self.default_expiration)
            await pipe.execute()

    def serialize(self, data: Any) -> str:
        """Serialize data to JSON string."""

        def datetime_handler(obj):
            if isinstance(obj, datetime):
                return obj.isoformat()
            return str(obj)

        return json.dumps(data, default=datetime_handler)

    def deserialize(self, data: str) -> Any:
        """Deserialize JSON string to data."""

        def datetime_parser(dct):
            for k, v in dct.items():
                if isinstance(v, str):
                    try:
                        dct[k] = datetime.fromisoformat(v)
                    except ValueError:
                        pass
            return dct

        return json.loads(data, object_hook=datetime_parser)


async def provide_redis_service() -> RedisService:
    """
    Provides a RedisService instance.

    Returns:
        RedisService: An instance of the RedisService class.
    """
    return RedisService()
