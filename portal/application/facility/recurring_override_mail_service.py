"""
Dispatch bilingual Priority Ministry override emails via MailSendPort.
"""

from collections import defaultdict
from datetime import date
from typing import Optional
from uuid import UUID

from portal.application.facility.recurring_override_mail_content import (
    EN_LOCALE_ID,
    OVERRIDE_SUBJECT,
    TEMPLATE_BOOKING_OVERRIDE,
    ZH_TW_LOCALE_ID,
    dedupe_emails,
    format_override_date_en,
    format_override_date_zh,
    room_name_for_locale,
)
from portal.application.facility.results import RecurringOverrideNotification, RecurringOverrideNotificationItem
from portal.application.org.ministry_application_mail_delivery import resolve_mail_delivery_targets
from portal.domain.email.ports import EmailTemplateRenderPort
from portal.domain.facility.constants import BOOKING_PAYMENT_RESOURCE_CODE
from portal.domain.org.constants import FACILITY_DEACON_POSITION_CODE
from portal.domain.org.ports import MailSendPort
from portal.infrastructure.persistence.repositories.facility.room_repository import RoomRepository
from portal.infrastructure.persistence.repositories.org.position_repository import PositionRepository
from portal.infrastructure.persistence.repositories.permission_repository import PermissionRepository
from portal.infrastructure.persistence.repositories.user_repository import UserRepository
from portal.libs.logger import logger
from portal.libs.tracing.distributed_trace import distributed_trace


class RecurringOverrideMailService:
    """Send bilingual override mail to Bookers, payment operators, and the Facility Deacon."""

    def __init__(
        self,
        mail_send_port: MailSendPort,
        email_template_render_port: EmailTemplateRenderPort,
        user_repository: UserRepository,
        permission_repository: PermissionRepository,
        position_repository: PositionRepository,
        room_repository: RoomRepository,
        *,
        facility_booking_base_url: str,
        enabled: bool,
        override_recipients: list[str] | None = None,
    ):
        self._mail_send_port = mail_send_port
        self._email_template_render_port = email_template_render_port
        self._user_repository = user_repository
        self._permission_repository = permission_repository
        self._position_repository = position_repository
        self._room_repository = room_repository
        self._facility_booking_base_url = facility_booking_base_url.rstrip("/")
        self._enabled = enabled
        self._override_recipients = override_recipients or []

    @distributed_trace()
    async def notify_priority_override(self, notification: RecurringOverrideNotification) -> None:
        """Each displaced Booker gets one mail linking their own Booking; staff get one mail covering every item."""
        if not self._enabled:
            return
        try:
            booker_emails: dict[UUID, str] = {}
            for booker_id in notification.affected_booker_ids:
                email = await self._active_user_email(booker_id)
                if email and email.lower() not in {value.lower() for value in booker_emails.values()}:
                    booker_emails[booker_id] = email
            for booker_id, email in booker_emails.items():
                booker_items = [item for item in notification.items if item.booker_id == booker_id]
                await self._deliver(email, await self._render_body(notification, booker_items))
            already_sent = {email.lower() for email in booker_emails.values()}
            staff_emails = [email for email in await self._list_staff_emails() if email.lower() not in already_sent]
            if staff_emails:
                body_html = await self._render_body(notification, notification.items)
                for email in staff_emails:
                    await self._deliver(email, body_html)
        except Exception:
            logger.exception("Failed to send Priority Ministry override emails for series %s", notification.series_id)

    async def _deliver(self, intended_recipient: str, body_html: str) -> None:
        recipients, subject_prefix = resolve_mail_delivery_targets(intended_recipient=intended_recipient, override_recipients=self._override_recipients)
        for to_email in recipients:
            await self._mail_send_port.send_html_mail(to_email=to_email, subject=f"{subject_prefix}{OVERRIDE_SUBJECT}", body_html=body_html)

    async def list_intended_recipient_emails(self, notification: RecurringOverrideNotification) -> list[str]:
        emails: list[str | None] = []
        for booker_id in notification.affected_booker_ids:
            emails.append(await self._active_user_email(booker_id))
        emails.extend(await self._list_staff_emails())
        return dedupe_emails(emails)

    async def _list_staff_emails(self) -> list[str]:
        emails: list[str | None] = list(await self._permission_repository.list_active_emails_for_resource_code(BOOKING_PAYMENT_RESOURCE_CODE))
        deacon_user_id = await self._position_repository.get_current_incumbent_user_id_by_code(FACILITY_DEACON_POSITION_CODE)
        if deacon_user_id:
            emails.append(await self._active_user_email(deacon_user_id))
        return dedupe_emails(emails)

    async def _active_user_email(self, user_id: UUID) -> Optional[str]:
        user = await self._user_repository.get_sensitive_by_id(user_id)
        if not user or not user.is_active or not user.email:
            return None
        return user.email

    async def _render_body(self, notification: RecurringOverrideNotification, items: list[RecurringOverrideNotificationItem]) -> str:
        facility_ids: list[UUID] = []
        for item in items:
            for facility_id in item.facility_ids:
                if facility_id not in facility_ids:
                    facility_ids.append(facility_id)
        rooms_by_id = {}
        for facility_id in facility_ids:
            rooms_by_id[facility_id] = await self._room_repository.get_by_id(facility_id, locale_id=None, all_locales=True)

        dates_to_facilities: dict[date, list[UUID]] = defaultdict(list)
        for item in items:
            for facility_id in item.facility_ids:
                if facility_id not in dates_to_facilities[item.occurrence_date]:
                    dates_to_facilities[item.occurrence_date].append(facility_id)

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

        detail_booking_id = items[0].booking_id if items else None
        my_bookings_url = f"{self._facility_booking_base_url}/my-bookings"
        if detail_booking_id:
            my_bookings_url = f"{my_bookings_url}/{detail_booking_id}"

        return await self._email_template_render_port.render_email_template(
            TEMPLATE_BOOKING_OVERRIDE,
            church_activity_name=notification.church_activity_name,
            church_activity_name_zh=notification.church_activity_name_zh or notification.church_activity_name,
            occurrence_lines_en=occurrence_lines_en,
            occurrence_lines_zh=occurrence_lines_zh,
            my_bookings_url=my_bookings_url,
        )
