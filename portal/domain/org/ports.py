"""
Organization domain ports.
"""

from typing import Protocol


class MailSendPort(Protocol):
    """Send a single HTML email message."""

    async def send_html_mail(self, *, to_email: str, subject: str, body_html: str) -> None: ...
