"""
Member web app registration (Origin -> app_code).
"""

from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse


@dataclass(frozen=True)
class MemberWebApp:
    """Registered member-facing SPA."""

    code: str
    origins: frozenset[str]


def normalize_origin(raw: str) -> Optional[str]:
    """
    Normalize an Origin or URL to scheme://host[:port] (no path).
    :param raw:
    :return:
    """
    value = (raw or "").strip()
    if not value:
        return None
    if "://" not in value:
        value = f"https://{value}"
    parsed = urlparse(value)
    if not parsed.scheme or not parsed.netloc:
        return None
    return f"{parsed.scheme.lower()}://{parsed.netloc.lower()}"


def parse_member_web_apps(raw: Optional[str]) -> list[MemberWebApp]:
    """
    Parse MEMBER_WEB_APPS env.

    Format (comma-separated apps; pipe-separated code|origin|origin...):
      facility-booking|http://localhost:5174|https://booking.example.com,
      another-app|http://localhost:5180

    :param raw:
    :return:
    """
    if not raw or not raw.strip():
        return []
    apps: list[MemberWebApp] = []
    for app_chunk in raw.split(","):
        parts = [p.strip() for p in app_chunk.strip().split("|") if p.strip()]
        if len(parts) < 2:
            continue
        code = parts[0]
        origins: set[str] = set()
        for origin_raw in parts[1:]:
            normalized = normalize_origin(origin_raw)
            if normalized:
                origins.add(normalized)
        if code and origins:
            apps.append(MemberWebApp(code=code, origins=frozenset(origins)))
    return apps


class MemberWebAppRegistry:
    """Resolve Origin / Referer to a registered member web app code."""

    def __init__(self, apps: list[MemberWebApp]):
        self._apps = list(apps)
        self._origin_to_code: dict[str, str] = {}
        for app in self._apps:
            for origin in app.origins:
                self._origin_to_code[origin] = app.code

    @property
    def apps(self) -> list[MemberWebApp]:
        return list(self._apps)

    def resolve_app_code(self, origin: Optional[str] = None, referer: Optional[str] = None) -> Optional[str]:
        """
        Resolve request Origin (preferred) or Referer to app_code.
        :param origin:
        :param referer:
        :return:
        """
        for candidate in (origin, referer):
            normalized = normalize_origin(candidate) if candidate else None
            if normalized and normalized in self._origin_to_code:
                return self._origin_to_code[normalized]
        return None
