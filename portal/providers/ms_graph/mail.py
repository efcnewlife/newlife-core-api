"""
MSGraphMail — send mail via Microsoft Graph Mail.Send (application permission).
"""

from msgraph_beta.generated.models.body_type import BodyType
from msgraph_beta.generated.models.email_address import EmailAddress
from msgraph_beta.generated.models.item_body import ItemBody
from msgraph_beta.generated.models.message import Message
from msgraph_beta.generated.models.o_data_errors.o_data_error import ODataError
from msgraph_beta.generated.models.recipient import Recipient
from msgraph_beta.generated.users.item.send_mail.send_mail_post_request_body import SendMailPostRequestBody

from portal.config import settings
from portal.libs.logger import logger
from portal.providers.ms_graph.base import MSGraphClientBase


class MSGraphMail(MSGraphClientBase):
    """Send HTML mail from a configured system mailbox."""

    def is_send_configured(self) -> bool:
        return self.is_configured() and bool(settings.GRAPH_MAIL_SENDER_MAILBOX)

    async def send_html_mail(self, *, to_email: str, subject: str, body_html: str) -> None:
        if not self.is_send_configured():
            raise RuntimeError("Microsoft Graph mail send is not configured")
        sender_mailbox = str(settings.GRAPH_MAIL_SENDER_MAILBOX).strip()
        normalized_to = (to_email or "").strip()
        if not normalized_to:
            raise ValueError("Recipient email is required")

        message = Message(
            subject=subject,
            body=ItemBody(content_type=BodyType.Html, content=body_html),
            to_recipients=[Recipient(email_address=EmailAddress(address=normalized_to))],
        )
        request_body = SendMailPostRequestBody(message=message, save_to_sent_items=False)
        try:
            await self.client.users.by_user_id(sender_mailbox).send_mail.post(request_body)
        except ODataError as exc:
            logger.error(
                "Graph send_mail failed: code=%s message=%s",
                getattr(exc.error, "code", None) if getattr(exc, "error", None) else None,
                getattr(exc.error, "message", None) if getattr(exc, "error", None) else str(exc),
            )
            raise
