import uuid
from typing import Optional
from uuid import UUID

from dependency_injector.wiring import inject, Provide
from fastapi import Request
from fastapi.datastructures import Headers
from starlette.middleware.base import BaseHTTPMiddleware

from portal.container import Container
from portal.application.locale.locale_service import LocaleService
from portal.libs.contexts.request_context import (
    RequestContext,
    set_request_context,
    reset_request_context,
)
from portal.libs.contexts.request_session_context import (
    set_request_session,
    reset_request_session,
)
from portal.application.auth.results import HeaderInfo


def _resolve_ip(request: Request) -> str | None:
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    xri = request.headers.get("x-real-ip")
    if xri:
        return xri.strip()
    return request.client.host if request.client else None


class CoreRequestMiddleware(BaseHTTPMiddleware):
    @classmethod
    def _normalize_locale_code(cls, locale_code: str) -> str:
        return locale_code.strip().replace("_", "-").lower()

    @classmethod
    def _parse_accept_language(cls, accept_language: Optional[str]) -> list[str]:
        if not accept_language:
            return []

        weighted_items: list[tuple[int, str, float]] = []
        for index, raw_item in enumerate(accept_language.split(",")):
            item = raw_item.strip()
            if not item:
                continue

            locale_code = item
            quality = 1.0
            if ";" in item:
                locale_code, *params = [part.strip() for part in item.split(";")]
                for param in params:
                    if not param.startswith("q="):
                        continue
                    try:
                        quality = float(param[2:])
                    except ValueError:
                        quality = 0.0
            if not locale_code:
                continue
            normalized_code = cls._normalize_locale_code(locale_code)
            quality = max(0.0, min(quality, 1.0))
            weighted_items.append((index, normalized_code, quality))

        weighted_items.sort(key=lambda value: (-value[2], value[0]))
        return [locale_code for _, locale_code, _ in weighted_items]

    @classmethod
    def _extract_locale_parts(cls, locale_code: str) -> tuple[str, Optional[str], Optional[str]]:
        parts = cls._normalize_locale_code(locale_code).split("-")
        language_code = parts[0] if parts else ""
        script_code = None
        region_code = None
        if len(parts) >= 2:
            # BCP 47: language-script-region
            if len(parts[1]) == 4:
                script_code = parts[1]
                if len(parts) >= 3:
                    region_code = parts[2]
            else:
                region_code = parts[1]
        return language_code, script_code, region_code

    @classmethod
    def _match_locale_by_language_script(
        cls,
        locale_codes: list[str],
        script_code: str,
    ) -> Optional[str]:
        for locale_code in locale_codes:
            parts = cls._normalize_locale_code(locale_code).split("-")
            if len(parts) >= 3 and parts[1] == script_code:
                return locale_code
        return None

    @classmethod
    def _match_locale_by_language_region(
        cls,
        locale_codes: list[str],
        region_code: str,
    ) -> Optional[str]:
        for locale_code in locale_codes:
            parts = cls._normalize_locale_code(locale_code).split("-")
            if len(parts) >= 3 and parts[2] == region_code:
                return locale_code
            if len(parts) == 2 and parts[1] == region_code:
                return locale_code
        return None

    async def dispatch(self, request: Request, call_next):
        req_ctx_token = None
        container: Container = request.app.container
        db_session = container.db_session()
        session_ctx_token = set_request_session(db_session)
        try:
            # initialize request context
            headers = await self.resolve_raw_headers(request.headers)
            resolved_locale_code, resolved_locale_id, locale_candidates = await self.locale_detector(headers.accept_language)
            req_ctx_token = set_request_context(
                RequestContext(
                    request_id=str(uuid.uuid4()),
                    ip=_resolve_ip(request),
                    client_ip=(request.client.host if request.client else None),
                    method=request.method,
                    host=(request.headers.get("host") or request.url.hostname),
                    url=str(request.url),
                    path=request.url.path,
                    headers=headers,
                    locale_candidates=locale_candidates,
                    resolved_locale_code=resolved_locale_code,
                    resolved_locale_id=resolved_locale_id,
                )
            )
            response = await call_next(request)
        except Exception as e:
            await db_session.rollback()
            raise e
        else:
            if resolved_locale_code:
                response.headers["Content-Language"] = resolved_locale_code
            await db_session.commit()
            return response
        finally:
            if req_ctx_token is not None:
                reset_request_context(req_ctx_token)
            await db_session.close()
            reset_request_session(session_ctx_token)

    async def resolve_raw_headers(self, headers: Headers) -> HeaderInfo:
        """

        :param headers:
        :return:
        """
        return HeaderInfo(
            user_agent=headers.get("user-agent"),
            accept_language=headers.get("accept-language"),
            host=headers.get("host"),
            referer=headers.get("referer"),
            origin=headers.get("origin"),
        )


    @inject
    async def locale_detector(
        self,
        accept_language: Optional[str],
        locale_service: LocaleService = Provide[Container.locale_service],
    ) -> tuple[Optional[str], Optional[UUID], list[str]]:
        """

        :param accept_language:
        :param locale_service:
        :return:
        """
        snapshot = await locale_service.get_locale_snapshot()
        ordered_active_locales = snapshot.get("active_locales", [])
        active_locales = set(ordered_active_locales)
        default_locale = snapshot.get("default_locale")
        normalized_map = snapshot.get("normalized_map", {})
        normalized_id_map = snapshot.get("normalized_id_map", {})
        locale_candidates = self._parse_accept_language(accept_language)

        def get_locale_id(locale_code: Optional[str]) -> Optional[UUID]:
            if not locale_code:
                return None
            locale_id = normalized_id_map.get(self._normalize_locale_code(locale_code))
            if not locale_id:
                return None
            try:
                return UUID(locale_id)
            except ValueError:
                return None

        language_cache: dict[str, list[str]] = {}
        for candidate in locale_candidates:
            if candidate == "*":
                if default_locale:
                    return default_locale, get_locale_id(default_locale), locale_candidates
                continue
            matched_locale = normalized_map.get(candidate)
            if matched_locale and matched_locale in active_locales:
                return matched_locale, get_locale_id(matched_locale), locale_candidates

            language_code, script_code, region_code = self._extract_locale_parts(candidate)
            if not language_code:
                continue
            if language_code not in language_cache:
                language_cache[language_code] = await locale_service.get_locale_codes_by_language(language_code)
            locale_codes = language_cache.get(language_code, [])
            if not locale_codes:
                continue

            if region_code:
                language_region_match = self._match_locale_by_language_region(locale_codes, region_code)
                if language_region_match:
                    return language_region_match, get_locale_id(language_region_match), locale_candidates

            if script_code:
                language_script_match = self._match_locale_by_language_script(locale_codes, script_code)
                if language_script_match:
                    return language_script_match, get_locale_id(language_script_match), locale_candidates
            selected_locale_code = locale_codes[0]
            return selected_locale_code, get_locale_id(selected_locale_code), locale_candidates

        if default_locale:
            return default_locale, get_locale_id(default_locale), locale_candidates
        if ordered_active_locales:
            selected_locale_code = ordered_active_locales[0]
            return selected_locale_code, get_locale_id(selected_locale_code), locale_candidates
        return None, None, locale_candidates
