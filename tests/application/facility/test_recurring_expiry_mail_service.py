"""
Tests for Pending-payment hold expiry mail.
"""

from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from portal.application.facility.recurring_expiry_mail_service import RecurringExpiryMailService
from portal.application.facility.recurring_override_mail_content import EXPIRY_SUBJECT, TEMPLATE_BOOKING_PAYMENT_HOLD_EXPIRED
from portal.application.facility.results import (
    RecurringBookingOccurrenceResult,
    RecurringPaymentHoldExpiryNotification,
    RoomDetailResult,
    TranslationItemResult,
)
from portal.domain.facility.constants import PENDING_PAYMENT_SWEEP_INTERVAL_SECONDS
from portal.providers.template_render_provider import TemplateRenderProvider
from tests.application.facility.test_recurring_override_mail_service import StubMailSendPort, StubMailUserRepository, _user
from tests.fixtures.facility.stubs import StubRoomRepository


def _mail_service(
    mail_port: StubMailSendPort,
    user_stub: StubMailUserRepository,
    room_stub: StubRoomRepository,
    *,
    enabled: bool = True,
    override_recipients: list[str] | None = None,
) -> RecurringExpiryMailService:
    return RecurringExpiryMailService(
        mail_port,
        TemplateRenderProvider(),
        user_stub,
        room_stub,
        facility_booking_base_url="http://localhost:5174",
        enabled=enabled,
        override_recipients=override_recipients,
    )


def _notification(*, booker_id: UUID, facility_id: UUID) -> RecurringPaymentHoldExpiryNotification:
    return RecurringPaymentHoldExpiryNotification(
        series_id=uuid4(),
        booker_id=booker_id,
        quoted_amount=Decimal("200.00"),
        currency="CAD",
        occurrences=[
            RecurringBookingOccurrenceResult(
                id=uuid4(),
                start_at=datetime(2026, 1, 13, 15, 0, tzinfo=timezone.utc),
                end_at=datetime(2026, 1, 13, 17, 0, tzinfo=timezone.utc),
                status="pending_payment",
                quoted_amount=Decimal("100.00"),
                currency="CAD",
                facility_ids=[facility_id],
            )
        ],
    )


def test_pending_payment_sweep_interval_is_fifteen_minutes():
    assert PENDING_PAYMENT_SWEEP_INTERVAL_SECONDS == 15 * 60


@pytest.mark.asyncio
async def test_expiry_mail_sends_bilingual_content_to_booker():
    booker_id = uuid4()
    facility_id = uuid4()
    mail_port = StubMailSendPort()
    room = RoomDetailResult(
        id=facility_id,
        code="GYM",
        name="Gym A",
        translations=[
            TranslationItemResult(locale_id=UUID("019dd0c8-69fa-7657-87bb-3b7255f5c5ae"), name="Gym A"),
            TranslationItemResult(locale_id=UUID("019dd0c8-7540-7601-bfd1-7939ce75c16a"), name="體育館 A"),
        ],
    )
    service = _mail_service(
        mail_port, StubMailUserRepository({booker_id: _user(booker_id, "booker@efcnewlife.org")}), StubRoomRepository(room_by_id={facility_id: room})
    )

    await service.notify_payment_hold_expired(_notification(booker_id=booker_id, facility_id=facility_id))

    assert len(mail_port.calls) == 1
    call = mail_port.calls[0]
    assert call["to_email"] == "booker@efcnewlife.org"
    assert call["subject"] == EXPIRY_SUBJECT
    body_html = call["body_html"]
    english_marker_index = body_html.index("English")
    zh_marker_index = body_html.index("中文")
    divider_index = body_html.index("border-top: 1px solid #e9f3f5")
    assert english_marker_index < divider_index < zh_marker_index
    en_section = body_html[english_marker_index:divider_index]
    zh_section = body_html[zh_marker_index:]
    assert "January 13, 2026" in en_section
    assert "Gym A" in en_section
    assert "CAD 200.00" in en_section
    assert "2026年1月13日" in zh_section
    assert "體育館 A" in zh_section
    assert "http://localhost:5174/start-booking" in body_html
    assert TEMPLATE_BOOKING_PAYMENT_HOLD_EXPIRED.endswith("booking_payment_hold_expired.html")


@pytest.mark.asyncio
async def test_expiry_mail_redirects_to_override_recipients():
    booker_id = uuid4()
    mail_port = StubMailSendPort()
    service = _mail_service(
        mail_port, StubMailUserRepository({booker_id: _user(booker_id, "booker@efcnewlife.org")}), StubRoomRepository(), override_recipients=["dev@local.test"]
    )

    await service.notify_payment_hold_expired(_notification(booker_id=booker_id, facility_id=uuid4()))

    assert mail_port.calls[0]["to_email"] == "dev@local.test"
    assert mail_port.calls[0]["subject"].startswith("[DEV -> booker@efcnewlife.org] ")


@pytest.mark.asyncio
async def test_expiry_mail_swallows_delivery_failure():
    booker_id = uuid4()

    class FailingMailPort(StubMailSendPort):
        async def send_html_mail(self, *, to_email: str, subject: str, body_html: str) -> None:
            raise RuntimeError("graph down")

    service = _mail_service(FailingMailPort(), StubMailUserRepository({booker_id: _user(booker_id, "booker@efcnewlife.org")}), StubRoomRepository())

    await service.notify_payment_hold_expired(_notification(booker_id=booker_id, facility_id=uuid4()))


@pytest.mark.asyncio
async def test_expiry_mail_skips_inactive_booker():
    booker_id = uuid4()
    mail_port = StubMailSendPort()
    service = _mail_service(mail_port, StubMailUserRepository({booker_id: _user(booker_id, "inactive@efcnewlife.org", is_active=False)}), StubRoomRepository())

    await service.notify_payment_hold_expired(_notification(booker_id=booker_id, facility_id=uuid4()))

    assert mail_port.calls == []
