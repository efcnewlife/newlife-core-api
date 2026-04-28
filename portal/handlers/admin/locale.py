"""
AdminLocaleHandler
"""
import json
from typing import Any

from redis.asyncio import Redis

from portal.libs.consts.cache_keys import CacheExpiry, CacheKeys
from portal.libs.database import Session, RedisPool
from portal.models import SystemLocale
from portal.schemas.locale import SLocale


class AdminLocaleHandler:
    """AdminLocaleHandler"""

    def __init__(
        self,
        session: Session,
        redis_client: RedisPool
    ):
        self._session = session
        self._redis_client: Redis = redis_client.create(db=0)

    async def get_locales(self):
        """

        :return:
        """
        local_list: list[SLocale] = await (
            self._session.select(
                SystemLocale.id,
                SystemLocale.language_code,
                SystemLocale.script_code,
                SystemLocale.region_code,
                SystemLocale.name,
                SystemLocale.native_name,
                SystemLocale.is_active,
                SystemLocale.is_default,
            )
            .where(SystemLocale.is_deleted == False)
            .order_by(SystemLocale.sequence)
            .fetch(as_model=SLocale)
        )
        return local_list

    @classmethod
    def _decode_redis_value(cls, value: Any) -> str:
        if isinstance(value, bytes):
            return value.decode("utf-8")
        return str(value)

    @classmethod
    def _normalize_locale_code(cls, code: str) -> str:
        return code.strip().replace("_", "-").lower()

    @classmethod
    def _build_locale_code(cls, locale: SLocale) -> str:
        parts = [locale.language_code]
        if locale.script_code:
            parts.append(locale.script_code)
        if locale.region_code:
            parts.append(locale.region_code)
        return "-".join(parts)

    @classmethod
    def _extract_language_code(cls, locale_code: str) -> str:
        return cls._normalize_locale_code(locale_code).split("-")[0]

    @classmethod
    def _build_language_key(cls, language_code: str) -> str:
        return (
            CacheKeys(resource="locale")
            .add_attribute("lang")
            .add_attribute("v1")
            .add_attribute(language_code)
            .build()
        )

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

    async def _populate_locale_cache(self, locales: list[SLocale]) -> dict[str, Any]:
        active_locales: list[str] = []
        normalized_map: dict[str, str] = {}
        normalized_id_map: dict[str, str] = {}
        language_buckets: dict[str, list[str]] = {}
        default_locale: str | None = None

        for locale in locales:
            if not locale.is_active:
                continue
            locale_code = self._build_locale_code(locale)
            normalized_code = self._normalize_locale_code(locale_code)
            if locale_code not in active_locales:
                active_locales.append(locale_code)
            normalized_map[normalized_code] = locale_code
            normalized_id_map[normalized_code] = str(locale.id)
            language_code = self._extract_language_code(locale_code)
            language_buckets.setdefault(language_code, [])
            if locale_code not in language_buckets[language_code]:
                language_buckets[language_code].append(locale_code)
            if locale.is_default and default_locale is None:
                default_locale = locale_code

        if default_locale is None and active_locales:
            default_locale = active_locales[0]

        await self.clear_locale_cache()
        locale_active_key = self._get_locale_active_key()
        locale_meta_key = self._get_locale_meta_key()
        locale_norm_key = self._get_locale_norm_key()
        locale_norm_id_key = self._get_locale_norm_id_key()
        locale_lang_keys_set_key = self._get_locale_lang_keys_set_key()
        if active_locales:
            await self._redis_client.sadd(locale_active_key, *active_locales)
            await self._redis_client.expire(locale_active_key, CacheExpiry.WEEK)

        await self._redis_client.hset(
            locale_meta_key,
            mapping={
                "default_locale": default_locale or "",
                "version": "2",
                "active_locales_json": json.dumps(active_locales),
                "language_buckets_json": json.dumps(language_buckets),
            },
        )
        await self._redis_client.expire(locale_meta_key, CacheExpiry.WEEK)

        if normalized_map:
            await self._redis_client.hset(locale_norm_key, mapping=normalized_map)
            await self._redis_client.expire(locale_norm_key, CacheExpiry.WEEK)
        if normalized_id_map:
            await self._redis_client.hset(locale_norm_id_key, mapping=normalized_id_map)
            await self._redis_client.expire(locale_norm_id_key, CacheExpiry.WEEK)

        return {
            "active_locales": active_locales,
            "default_locale": default_locale,
            "normalized_map": normalized_map,
            "normalized_id_map": normalized_id_map,
            "language_buckets": language_buckets,
        }

    async def get_locale_snapshot(self) -> dict[str, Any]:
        active_raw = await self._redis_client.smembers(self._get_locale_active_key())
        meta_raw = await self._redis_client.hgetall(self._get_locale_meta_key())
        norm_raw = await self._redis_client.hgetall(self._get_locale_norm_key())
        norm_id_raw = await self._redis_client.hgetall(self._get_locale_norm_id_key())

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
            return {
                "active_locales": active_locales,
                "default_locale": default_locale,
                "normalized_map": normalized_map,
                "normalized_id_map": normalized_id_map,
                "language_buckets": language_buckets,
            }

        locales = await self.get_locales()
        return await self._populate_locale_cache(locales=locales)

    async def get_locale_codes_by_language(self, language_code: str) -> list[str]:
        normalized_language = self._normalize_locale_code(language_code)
        snapshot = await self.get_locale_snapshot()
        language_buckets: dict[str, list[str]] = snapshot.get("language_buckets", {})
        return language_buckets.get(normalized_language, [])

    async def clear_locale_cache(self) -> None:
        locale_active_key = self._get_locale_active_key()
        locale_meta_key = self._get_locale_meta_key()
        locale_norm_key = self._get_locale_norm_key()
        locale_norm_id_key = self._get_locale_norm_id_key()
        locale_lang_keys_set_key = self._get_locale_lang_keys_set_key()
        language_keys = await self._redis_client.smembers(locale_lang_keys_set_key)
        delete_keys = [
            locale_active_key,
            locale_meta_key,
            locale_norm_key,
            locale_norm_id_key,
            locale_lang_keys_set_key,
        ]
        if language_keys:
            delete_keys.extend(self._decode_redis_value(v) for v in language_keys)
        await self._redis_client.delete(*delete_keys)
