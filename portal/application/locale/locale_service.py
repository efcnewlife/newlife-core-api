"""
Locale application service.
"""
from typing import Any

from portal.application.locale.results import LocaleListResult, LocaleSnapshotResult
from portal.domain.locale.entities import Locale
from portal.domain.locale.ports import LocaleRepositoryPort
from portal.infrastructure.cache.locale_cache import LocaleCache
from portal.libs.tracing.distributed_trace import distributed_trace


class LocaleService:
    """Admin locale list and Redis-backed locale resolution snapshot."""

    def __init__(
        self,
        locale_repository: LocaleRepositoryPort,
        locale_cache: LocaleCache,
    ):
        self._repository = locale_repository
        self._cache = locale_cache

    @staticmethod
    def _normalize_locale_code(code: str) -> str:
        return code.strip().replace("_", "-").lower()

    @classmethod
    def _build_locale_code(cls, locale: Locale) -> str:
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
    def _build_snapshot_from_locales(cls, locales: list[Locale]) -> LocaleSnapshotResult:
        active_locales: list[str] = []
        normalized_map: dict[str, str] = {}
        normalized_id_map: dict[str, str] = {}
        language_buckets: dict[str, list[str]] = {}
        default_locale: str | None = None

        for locale in locales:
            if not locale.is_active:
                continue
            locale_code = cls._build_locale_code(locale)
            normalized_code = cls._normalize_locale_code(locale_code)
            if locale_code not in active_locales:
                active_locales.append(locale_code)
            normalized_map[normalized_code] = locale_code
            normalized_id_map[normalized_code] = str(locale.id)
            language_code = cls._extract_language_code(locale_code)
            language_buckets.setdefault(language_code, [])
            if locale_code not in language_buckets[language_code]:
                language_buckets[language_code].append(locale_code)
            if locale.is_default and default_locale is None:
                default_locale = locale_code

        if default_locale is None and active_locales:
            default_locale = active_locales[0]

        return LocaleSnapshotResult(
            active_locales=active_locales,
            default_locale=default_locale,
            normalized_map=normalized_map,
            normalized_id_map=normalized_id_map,
            language_buckets=language_buckets,
        )

    @distributed_trace()
    async def get_locales(self) -> list[Locale]:
        """
        Load all non-deleted locales.
        :return:
        """
        return await self._repository.list_all()

    @distributed_trace()
    async def get_locale_list_result(self) -> LocaleListResult:
        """
        Return domain locale list result.
        :return:
        """
        items = await self.get_locales()
        return LocaleListResult(items=items)

    @distributed_trace()
    async def get_locale_snapshot(self) -> dict[str, Any]:
        """
        Return locale resolution snapshot, loading from DB and caching on miss.
        :return:
        """
        cached = await self._cache.get_snapshot()
        if cached is not None:
            return cached.as_dict()
        locales = await self.get_locales()
        snapshot = self._build_snapshot_from_locales(locales)
        await self._cache.populate(snapshot)
        return snapshot.as_dict()

    @distributed_trace()
    async def get_locale_codes_by_language(self, language_code: str) -> list[str]:
        """
        Return active locale codes for a language prefix.
        :param language_code:
        :return:
        """
        normalized_language = self._normalize_locale_code(language_code)
        snapshot = await self.get_locale_snapshot()
        language_buckets: dict[str, list[str]] = snapshot.get("language_buckets", {})
        return language_buckets.get(normalized_language, [])

    @distributed_trace()
    async def clear_locale_cache(self) -> None:
        """
        Clear locale snapshot cache.
        :return:
        """
        await self._cache.clear()
