"""
Locale domain ports.
"""
from typing import Protocol

from portal.domain.locale.entities import Locale


class LocaleRepositoryPort(Protocol):
    """Load system locales."""

    async def list_all(self) -> list[Locale]:
        ...
