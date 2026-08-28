"""
Organization domain ports.
"""

from typing import Optional, Protocol
from uuid import UUID


class MailSendPort(Protocol):
    """Send a single HTML email message."""

    async def send_html_mail(self, *, to_email: str, subject: str, body_html: str) -> None: ...


class MinistryTypeNameLookupPort(Protocol):
    """Resolve translated ministry type catalog labels for mail."""

    async def get_translated_name_by_id(self, ministry_type_id: UUID, locale_id: UUID) -> Optional[str]:
        """Return translated ministry type name for a locale, if present."""
