"""
Dispatch bilingual ministry application emails via MailSendPort.
"""

from typing import Optional
from uuid import UUID

from portal.application.org.ministry_application_mail_content import (
    APPLICANT_APPROVED_SUBJECT,
    APPLICANT_REJECTED_SUBJECT,
    APPLICANT_SUBMIT_SUBJECT,
    EN_LOCALE_ID,
    INCUMBENT_NOTIFICATION_SUBJECT,
    INCUMBENT_STAFF_DECISION_SUBJECT,
    TEMPLATE_APPLICANT_DECISION_APPROVED,
    TEMPLATE_APPLICANT_DECISION_REJECTED,
    TEMPLATE_APPLICANT_SUBMIT_CONFIRMATION,
    TEMPLATE_INCUMBENT_NOTIFICATION,
    TEMPLATE_INCUMBENT_STAFF_DECISION_NOTIFICATION,
    ZH_CN_LOCALE_ID,
    ZH_TW_LOCALE_ID,
    build_application_summary_context,
    format_target_audience_names,
    resolve_bilingual_ministry_names,
    resolve_ministry_type_names_for_mail,
    resolve_staff_display_name,
    resolve_user_display_name,
)
from portal.application.org.ministry_application_mail_delivery import resolve_mail_delivery_targets
from portal.domain.email.ports import EmailTemplateRenderPort
from portal.domain.org.constants import MinistryDecisionChannel
from portal.domain.org.ports import MailSendPort, MinistryTypeNameLookupPort
from portal.infrastructure.persistence.repositories.org.ministry_repository import MinistryRepository
from portal.infrastructure.persistence.repositories.org.position_repository import PositionRepository
from portal.infrastructure.persistence.repositories.user_repository import UserRepository
from portal.libs.logger import logger
from portal.libs.tracing.distributed_trace import distributed_trace


class MinistryApplicationMailService:
    """Send applicant and incumbent emails for ministry application workflow."""

    def __init__(
        self,
        mail_send_port: MailSendPort,
        email_template_render_port: EmailTemplateRenderPort,
        ministry_repository: MinistryRepository,
        ministry_type_repository: MinistryTypeNameLookupPort,
        position_repository: PositionRepository,
        user_repository: UserRepository,
        *,
        facility_booking_base_url: str,
        enabled: bool,
        override_recipients: list[str] | None = None,
    ):
        self._mail_send_port = mail_send_port
        self._email_template_render_port = email_template_render_port
        self._ministry_repository = ministry_repository
        self._ministry_type_repository = ministry_type_repository
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

    async def _render(self, template_name: str, **context: object) -> str:
        return await self._email_template_render_port.render_email_template(template_name, **context)

    async def _list_target_audiences_zh(self, ministry_id: UUID):
        zh_tw_audiences = await self._ministry_repository.list_target_audiences(ministry_id, ZH_TW_LOCALE_ID)
        if format_target_audience_names(zh_tw_audiences) != "—":
            return zh_tw_audiences
        return await self._ministry_repository.list_target_audiences(ministry_id, ZH_CN_LOCALE_ID)

    async def _build_application_summary(self, *, ministry, applicant_display_name: str):
        code_fallback = ministry.ministry_type_code or (ministry.ministry_type.code if ministry.ministry_type else None)
        ministry_type_name_en, ministry_type_name_zh = await resolve_ministry_type_names_for_mail(
            self._ministry_type_repository, ministry_type_id=ministry.ministry_type_id, code_fallback=code_fallback
        )
        target_audiences_en = await self._ministry_repository.list_target_audiences(ministry.id, EN_LOCALE_ID)
        target_audiences_zh = await self._list_target_audiences_zh(ministry.id)
        return build_application_summary_context(
            ministry=ministry,
            applicant_display_name=applicant_display_name,
            ministry_type_name_en=ministry_type_name_en,
            ministry_type_name_zh=ministry_type_name_zh,
            target_audience_names_en=format_target_audience_names(target_audiences_en),
            target_audience_names_zh=format_target_audience_names(target_audiences_zh),
        )

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
                body_html = await self._render(
                    TEMPLATE_APPLICANT_SUBMIT_CONFIRMATION,
                    ministry_name_en=ministry_name_en,
                    ministry_name_zh=ministry_name_zh,
                    my_ministry_url=my_ministry_url,
                )
                await self._deliver_html_mail(intended_recipient=applicant.email, subject=APPLICANT_SUBMIT_SUBJECT, body_html=body_html)

            incumbent_user_id = await self._position_repository.get_current_incumbent_user_id(owner_position_id)
            if not incumbent_user_id:
                logger.warning("Skip incumbent submit mail: position %s has no incumbent", owner_position_id)
                return

            incumbent = await self._user_repository.get_sensitive_by_id(incumbent_user_id)
            if not incumbent or not incumbent.email:
                logger.warning("Skip incumbent submit mail: incumbent user %s has no email", incumbent_user_id)
                return

            applicant_display_name = await resolve_user_display_name(self._user_repository, applicant_user_id)
            application_summary = await self._build_application_summary(ministry=ministry, applicant_display_name=applicant_display_name)
            body_html = await self._render(
                TEMPLATE_INCUMBENT_NOTIFICATION,
                ministry_name_en=ministry_name_en,
                ministry_name_zh=ministry_name_zh,
                applicant_display_name=applicant_display_name,
                approval_detail_url=approval_detail_url,
                application_summary=application_summary,
            )
            await self._deliver_html_mail(intended_recipient=incumbent.email, subject=INCUMBENT_NOTIFICATION_SUBJECT, body_html=body_html)
        except Exception:
            logger.exception("Failed to send ministry application submit emails for ministry %s", ministry_id)

    @distributed_trace()
    async def send_decision_notification(
        self,
        *,
        ministry_id: UUID,
        applicant_user_id: Optional[UUID],
        approved: bool,
        decision_channel: MinistryDecisionChannel,
        decided_by_user_id: UUID,
        owner_position_id: UUID,
        rejection_reason: Optional[str] = None,
    ) -> None:
        if not self._enabled:
            return

        try:
            ministry = await self._ministry_repository.get_by_id(ministry_id, all_locales=True)
            if not ministry:
                logger.warning("Skip ministry decision mail: ministry %s not found", ministry_id)
                return

            resolved_applicant_id = applicant_user_id or ministry.submitted_by_id
            if not resolved_applicant_id:
                logger.warning("Skip ministry decision mail: ministry %s has no applicant", ministry_id)
                return

            applicant = await self._user_repository.get_sensitive_by_id(resolved_applicant_id)
            if not applicant or not applicant.email:
                logger.warning("Skip ministry decision mail: applicant %s has no email", resolved_applicant_id)
                return

            ministry_name_en, ministry_name_zh = resolve_bilingual_ministry_names(ministry.translations, ministry.name)
            my_ministry_url = f"{self._facility_booking_base_url}/my-ministry"
            channel_value = decision_channel.value
            staff_display_name: Optional[str] = None
            incumbent_display_name: Optional[str] = None

            if decision_channel == MinistryDecisionChannel.STAFF:
                staff_display_name = await resolve_staff_display_name(self._user_repository, decided_by_user_id)
                incumbent_user_id = await self._position_repository.get_current_incumbent_user_id(owner_position_id)
                incumbent_display_name = await resolve_user_display_name(self._user_repository, incumbent_user_id, fallback="Owner incumbent")

            if approved:
                subject = APPLICANT_APPROVED_SUBJECT
                template_name = TEMPLATE_APPLICANT_DECISION_APPROVED
                template_context: dict[str, object] = {
                    "ministry_name_en": ministry_name_en,
                    "ministry_name_zh": ministry_name_zh,
                    "my_ministry_url": my_ministry_url,
                    "decision_channel": channel_value,
                    "staff_display_name": staff_display_name,
                    "incumbent_display_name": incumbent_display_name,
                }
            else:
                reason = (rejection_reason or ministry.rejection_reason or "No reason provided").strip()
                subject = APPLICANT_REJECTED_SUBJECT
                template_name = TEMPLATE_APPLICANT_DECISION_REJECTED
                template_context = {
                    "ministry_name_en": ministry_name_en,
                    "ministry_name_zh": ministry_name_zh,
                    "my_ministry_url": my_ministry_url,
                    "rejection_reason": reason,
                    "decision_channel": channel_value,
                    "staff_display_name": staff_display_name,
                    "incumbent_display_name": incumbent_display_name,
                }

            body_html = await self._render(template_name, **template_context)
            await self._deliver_html_mail(intended_recipient=applicant.email, subject=subject, body_html=body_html)

            if decision_channel != MinistryDecisionChannel.STAFF:
                return

            incumbent_user_id = await self._position_repository.get_current_incumbent_user_id(owner_position_id)
            if not incumbent_user_id:
                logger.warning("Skip incumbent staff-decision mail: position %s has no incumbent", owner_position_id)
                return
            incumbent = await self._user_repository.get_sensitive_by_id(incumbent_user_id)
            if not incumbent or not incumbent.email:
                logger.warning("Skip incumbent staff-decision mail: incumbent user %s has no email", incumbent_user_id)
                return

            staff_body_html = await self._render(
                TEMPLATE_INCUMBENT_STAFF_DECISION_NOTIFICATION,
                ministry_name_en=ministry_name_en,
                ministry_name_zh=ministry_name_zh,
                staff_display_name=staff_display_name,
                approved=approved,
                rejection_reason=template_context.get("rejection_reason"),
            )
            await self._deliver_html_mail(intended_recipient=incumbent.email, subject=INCUMBENT_STAFF_DECISION_SUBJECT, body_html=staff_body_html)
        except Exception:
            logger.exception("Failed to send ministry application decision email for ministry %s", ministry_id)
