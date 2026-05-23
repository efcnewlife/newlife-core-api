"""
Redis snapshot cache for locale resolution.
"""
import json
from typing import Any

from redis.asyncio import Redis

from portal.application.locale.results import LocaleSnapshotResult
from portal.config import settings
from portal.domain.locale.entities import Locale
from portal.libs.consts.cache_keys import CacheExpiry, CacheKeys
from portal.libs.database import RedisPool


class LocaleCache:
    """Active locale set, meta hash, and normalization maps in Redis."""

    def __init__(self, redis_client: RedisPool):
        self._redis: Redis = redis_client.create(db=settings.REDIS_DB)

    @staticmethod
    def _decode_redis_value(value: Any) -> str:
        if isinstance(value, bytes):
            return value.decode("utf-8")
        return str(value)

    @classmethod
    def _get_locale_active_key(cls) -> str:
        return CacheKeys(resource="locale").add_attribute("active").add_attribute("v1").build()

    @classmethod
    def _get_locale_meta_key(cls) -> str:
        return CacheKeys(resource="locale").add_attribute("meta").add_attribute("v1").build()

    @classmethod
    def _get_locale_norm_key(cls) -> str:
        return CacheKeys(resource="locale").add_attribute("norm").add_attribute("v1").build()

    @classmethod
    def _get_locale_norm_id_key(cls) -> str:
        return CacheKeys(resource="locale").add_attribute("norm_id").add_attribute("v1").build()

    @classmethod
    def _get_locale_lang_keys_set_key(cls) -> str:
        return CacheKeys(resource="locale").add_attribute("lang_keys").add_attribute("v1").build()

    async def get_snapshot(self) -> LocaleSnapshotResult | None:
        """
        Read locale snapshot from Redis when fully populated.
        :return:
        """
        active_raw = await self._redis.smembers(self._get_locale_active_key())
        meta_raw = await self._redis.hgetall(self._get_locale_meta_key())
        norm_raw = await self._redis.hgetall(self._get_locale_norm_key())
        norm_id_raw = await self._redis.hgetall(self._get_locale_norm_id_key())

        active_locales = sorted([self._decode_redis_value(v) for v in active_raw]) if active_raw else []
        meta = (
            {self._decode_redis_value(k): self._decode_redis_value(v) for k, v in meta_raw.items()}
            if meta_raw else {}
        )
        normalized_map = (
            {self._decode_redis_value(k): self._decode_redis_value(v) for k, v in norm_raw.items()}
            if norm_raw else {}
        )
        normalized_id_map = (
            {self._decode_redis_value(k): self._decode_redis_value(v) for k, v in norm_id_raw.items()}
            if norm_id_raw else {}
        )
        default_locale = meta.get("default_locale") or None
        meta_active_locales = meta.get("active_locales_json")
        if meta_active_locales:
            try:
                active_locales = json.loads(meta_active_locales)
            except json.JSONDecodeError:
                pass
        language_buckets: dict[str, list[str]] = {}
        raw_language_buckets = meta.get("language_buckets_json")
        if raw_language_buckets:
            try:
                language_buckets = json.loads(raw_language_buckets)
            except json.JSONDecodeError:
                language_buckets = {}

        if active_locales and default_locale and normalized_map and normalized_id_map:
            return LocaleSnapshotResult(
                active_locales=active_locales,
                default_locale=default_locale,
                normalized_map=normalized_map,
                normalized_id_map=normalized_id_map,
                language_buckets=language_buckets,
            )
        return None

    async def populate(self, snapshot: LocaleSnapshotResult) -> None:
        """
        Write locale snapshot structures to Redis.
        :param snapshot:
        :return:
        """
        await self.clear()
        locale_active_key = self._get_locale_active_key()
        locale_meta_key = self._get_locale_meta_key()
        locale_norm_key = self._get_locale_norm_key()
        locale_norm_id_key = self._get_locale_norm_id_key()
        active_locales = snapshot.active_locales
        if active_locales:
            await self._redis.sadd(locale_active_key, *active_locales)
            await self._redis.expire(locale_active_key, CacheExpiry.WEEK)

        await self._redis.hset(
            locale_meta_key,
            mapping={
                "default_locale": snapshot.default_locale or "",
                "version": "2",
                "active_locales_json": json.dumps(active_locales),
                "language_buckets_json": json.dumps(snapshot.language_buckets),
            },
        )
        await self._redis.expire(locale_meta_key, CacheExpiry.WEEK)

        if snapshot.normalized_map:
            await self._redis.hset(locale_norm_key, mapping=snapshot.normalized_map)
            await self._redis.expire(locale_norm_key, CacheExpiry.WEEK)
        if snapshot.normalized_id_map:
            await self._redis.hset(locale_norm_id_key, mapping=snapshot.normalized_id_map)
            await self._redis.expire(locale_norm_id_key, CacheExpiry.WEEK)

    async def clear(self) -> None:
        """
        Remove locale snapshot keys from Redis.
        :return:
        """
        locale_active_key = self._get_locale_active_key()
        locale_meta_key = self._get_locale_meta_key()
        locale_norm_key = self._get_locale_norm_key()
        locale_norm_id_key = self._get_locale_norm_id_key()
        locale_lang_keys_set_key = self._get_locale_lang_keys_set_key()
        language_keys = await self._redis.smembers(locale_lang_keys_set_key)
        delete_keys = [
            locale_active_key,
            locale_meta_key,
            locale_norm_key,
            locale_norm_id_key,
            locale_lang_keys_set_key,
        ]
        if language_keys:
            delete_keys.extend(self._decode_redis_value(v) for v in language_keys)
        await self._redis.delete(*delete_keys)
