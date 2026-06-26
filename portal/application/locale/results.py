"""
Locale application results.
"""
from typing import Any, Optional

from pydantic import BaseModel, Field

from portal.domain.locale.entities import Locale


class LocaleListResult(BaseModel):
    """Result of listing all system locales."""

    items: list[Locale] = Field(default_factory=list)


class LocaleSnapshotResult(BaseModel):
    """Redis-backed locale resolution snapshot."""

    active_locales: list[str] = Field(default_factory=list)
    default_locale: Optional[str] = Field(None)
    normalized_map: dict[str, str] = Field(default_factory=dict)
    normalized_id_map: dict[str, str] = Field(default_factory=dict)
    language_buckets: dict[str, list[str]] = Field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        """
        Return snapshot as a plain dict for middleware compatibility.
        :return:
        """
        return self.model_dump()
