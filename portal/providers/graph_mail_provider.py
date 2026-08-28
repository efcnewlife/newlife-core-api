"""
Microsoft Graph mail send facade.
"""

from collections.abc import Callable

from portal.providers.ms_graph.mail import MSGraphMail

__all__ = ["GraphMailProvider"]


class GraphMailProvider:
    """Send HTML mail using app-only Graph Mail.Send."""

    def __init__(self, mail_factory: Callable[[], MSGraphMail] = MSGraphMail) -> None:
        self._mail_factory = mail_factory

    def is_configured(self) -> bool:
        return self._mail_factory().is_send_configured()

    async def send_html_mail(self, *, to_email: str, subject: str, body_html: str) -> None:
        await self._mail_factory().send_html_mail(to_email=to_email, subject=subject, body_html=body_html)
