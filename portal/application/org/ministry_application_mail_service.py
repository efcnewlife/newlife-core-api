"""
Dispatch bilingual ministry application submit emails via MailSendPort.
"""

from typing import Optional
from uuid import UUID

from portal.application.org.ministry_application_mail_content import (
    APPLICANT_SUBMIT_SUBJECT,
    INCUMBENT_NOTIFICATION_SUBJECT,
    build_applicant_submit_confirmation_html,
    build_incumbent_notification_html,
    resolve_bilingual_ministry_names,
)
from portal.application.org.ministry_application_mail_delivery import resolve_mail_delivery_targets
from portal.domain.org.ports import MailSendPort
from portal.infrastructure.persistence.repositories.org.ministry_repository import MinistryRepository
from portal.infrastructure.persistence.repositories.org.position_repository import PositionRepository
from portal.infrastructure.persistence.repositories.user_repository import UserRepository
from portal.libs.logger import logger
from portal.libs.tracing.distributed_trace import distributed_trace


class MinistryApplicationMailService:
    """Send applicant and incumbent emails after ministry application submit."""

    def __init__(
        self,
        mail_send_port: MailSendPort,
        ministry_repository: MinistryRepository,
        position_repository: PositionRepository,
        user_repository: UserRepository,
        *,
        facility_booking_base_url: str,
        enabled: bool,
        override_recipients: list[str] | None = None,
    ):
        self._mail_send_port = mail_send_port
        self._ministry_repository = ministry_repository
        self._position_repository = position_repository
        self._user_repository = user_repository
        self._facility_booking_base_url = facility_booking_base_url.rstrip("/")
        self._enabled = enabled
        self._override_recipients = override_recipients or []

    async def _deliver_html_mail(self, *, intended_recipient: str, subject: str, body_html: str) -> None:
        recipients, subject_prefix = resolve_mail_delivery_targets(intended_recipient=intended_recipient, override_recipients=self._override_recipients)
        if not recipients:
            return
        delivery_subject = f"{subject_prefix}{subject}"
        for to_email in recipients:
            await self._mail_send_port.send_html_mail(to_email=to_email, subject=delivery_subject, body_html=body_html)

    @distributed_trace()
    async def send_submit_notifications(self, *, ministry_id: UUID, owner_position_id: UUID, applicant_user_id: Optional[UUID]) -> None:
        if not self._enabled:
            return

        try:
            ministry = await self._ministry_repository.get_by_id(ministry_id, all_locales=True)
            if not ministry:
                logger.warning("Skip ministry submit mail: ministry %s not found", ministry_id)
                return

            ministry_name_en, ministry_name_zh = resolve_bilingual_ministry_names(ministry.translations, ministry.name)
            my_ministry_url = f"{self._facility_booking_base_url}/my-ministry"
            approval_detail_url = f"{self._facility_booking_base_url}/my-ministry/approvals/{ministry_id}"

            applicant = await self._user_repository.get_sensitive_by_id(applicant_user_id) if applicant_user_id else None
            if applicant and applicant.email:
                await self._deliver_html_mail(
                    intended_recipient=applicant.email,
                    subject=APPLICANT_SUBMIT_SUBJECT,
                    body_html=build_applicant_submit_confirmation_html(
                        ministry_name_en=ministry_name_en, ministry_name_zh=ministry_name_zh, my_ministry_url=my_ministry_url
                    ),
                )

            incumbent_user_id = await self._position_repository.get_current_incumbent_user_id(owner_position_id)
            if not incumbent_user_id:
                logger.warning("Skip incumbent submit mail: position %s has no incumbent", owner_position_id)
                return

            incumbent = await self._user_repository.get_sensitive_by_id(incumbent_user_id)
            if not incumbent or not incumbent.email:
                logger.warning("Skip incumbent submit mail: incumbent user %s has no email", incumbent_user_id)
                return

            applicant_display_name = "Applicant"
            if applicant_user_id:
                applicant_profile = await self._user_repository.get_detail_by_id(applicant_user_id)
                if applicant_profile and applicant_profile.preferred_name:
                    applicant_display_name = applicant_profile.preferred_name
                elif applicant and applicant.email:
                    applicant_display_name = applicant.email

            await self._deliver_html_mail(
                intended_recipient=incumbent.email,
                subject=INCUMBENT_NOTIFICATION_SUBJECT,
                body_html=build_incumbent_notification_html(
                    ministry_name_en=ministry_name_en,
                    ministry_name_zh=ministry_name_zh,
                    applicant_display_name=applicant_display_name,
                    approval_detail_url=approval_detail_url,
                ),
            )
        except Exception:
            logger.exception("Failed to send ministry application submit emails for ministry %s", ministry_id)
