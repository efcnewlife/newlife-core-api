"""
Dispatch bilingual Pending-payment hold expiry emails via MailSendPort.
"""

from collections import defaultdict
from datetime import date
from decimal import Decimal
from typing import Optional
from uuid import UUID

from portal.application.facility.recurring_override_mail_content import (
    EN_LOCALE_ID,
    EXPIRY_SUBJECT,
    TEMPLATE_BOOKING_PAYMENT_HOLD_EXPIRED,
    ZH_TW_LOCALE_ID,
    format_override_date_en,
    format_override_date_zh,
    room_name_for_locale,
)
from portal.application.facility.results import RecurringPaymentHoldExpiryNotification
from portal.application.org.ministry_application_mail_delivery import resolve_mail_delivery_targets
from portal.domain.email.ports import EmailTemplateRenderPort
from portal.domain.org.ports import MailSendPort
from portal.infrastructure.persistence.repositories.facility.room_repository import RoomRepository
from portal.infrastructure.persistence.repositories.user_repository import UserRepository
from portal.libs.logger import logger
from portal.libs.tracing.distributed_trace import distributed_trace


class RecurringExpiryMailService:
    """Send bilingual Pending-payment hold expiry mail to the Booker."""

    def __init__(
        self,
        mail_send_port: MailSendPort,
        email_template_render_port: EmailTemplateRenderPort,
        user_repository: UserRepository,
        room_repository: RoomRepository,
        *,
        facility_booking_base_url: str,
        enabled: bool,
        override_recipients: list[str] | None = None,
    ):
        self._mail_send_port = mail_send_port
        self._email_template_render_port = email_template_render_port
        self._user_repository = user_repository
        self._room_repository = room_repository
        self._facility_booking_base_url = facility_booking_base_url.rstrip("/")
        self._enabled = enabled
        self._override_recipients = override_recipients or []

    @distributed_trace()
    async def notify_payment_hold_expired(self, notification: RecurringPaymentHoldExpiryNotification) -> None:
        if not self._enabled:
            return
        try:
            booker_email = await self._active_user_email(notification.booker_id)
            if not booker_email:
                return
            body_html = await self._render_body(notification)
            recipients, subject_prefix = resolve_mail_delivery_targets(intended_recipient=booker_email, override_recipients=self._override_recipients)
            if not recipients:
                return
            delivery_subject = f"{subject_prefix}{EXPIRY_SUBJECT}"
            for to_email in recipients:
                await self._mail_send_port.send_html_mail(to_email=to_email, subject=delivery_subject, body_html=body_html)
        except Exception:
            logger.exception("Failed to send Pending-payment hold expiry email for series %s", notification.series_id)

    async def _active_user_email(self, user_id: UUID) -> Optional[str]:
        user = await self._user_repository.get_sensitive_by_id(user_id)
        if not user or not user.is_active or not user.email:
            return None
        return user.email

    async def _render_body(self, notification: RecurringPaymentHoldExpiryNotification) -> str:
        facility_ids: list[UUID] = []
        for item in notification.occurrences:
            for facility_id in item.facility_ids:
                if facility_id not in facility_ids:
                    facility_ids.append(facility_id)
        rooms_by_id = {}
        for facility_id in facility_ids:
            rooms_by_id[facility_id] = await self._room_repository.get_by_id(facility_id, locale_id=None, all_locales=True)

        dates_to_facilities: dict[date, list[UUID]] = defaultdict(list)
        for item in notification.occurrences:
            occurrence_date = item.start_at.date()
            for facility_id in item.facility_ids:
                if facility_id not in dates_to_facilities[occurrence_date]:
                    dates_to_facilities[occurrence_date].append(facility_id)

        occurrence_lines_en: list[str] = []
        occurrence_lines_zh: list[str] = []
        for occurrence_date in sorted(dates_to_facilities):
            en_rooms = [
                room_name_for_locale(rooms_by_id.get(facility_id), EN_LOCALE_ID, str(facility_id)) for facility_id in dates_to_facilities[occurrence_date]
            ]
            zh_rooms = [
                room_name_for_locale(rooms_by_id.get(facility_id), ZH_TW_LOCALE_ID, str(facility_id)) for facility_id in dates_to_facilities[occurrence_date]
            ]
            occurrence_lines_en.append(f"{format_override_date_en(occurrence_date)} — {', '.join(en_rooms)}")
            occurrence_lines_zh.append(f"{format_override_date_zh(occurrence_date)} — {', '.join(zh_rooms)}")

        quoted_amount = notification.quoted_amount if isinstance(notification.quoted_amount, Decimal) else Decimal(str(notification.quoted_amount))
        payment_total = f"{notification.currency} {quoted_amount.quantize(Decimal('0.01'))}"
        start_booking_url = f"{self._facility_booking_base_url}/start-booking"
        return await self._email_template_render_port.render_email_template(
            TEMPLATE_BOOKING_PAYMENT_HOLD_EXPIRED,
            occurrence_lines_en=occurrence_lines_en,
            occurrence_lines_zh=occurrence_lines_zh,
            payment_total=payment_total,
            start_booking_url=start_booking_url,
        )
