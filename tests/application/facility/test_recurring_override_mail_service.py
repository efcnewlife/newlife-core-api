"""
Tests for Priority Ministry override mail recipients and bilingual content.
"""

from datetime import date
from uuid import UUID, uuid4

import pytest

from portal.application.auth.results import UserSensitive
from portal.application.facility.recurring_override_mail_content import OVERRIDE_SUBJECT, TEMPLATE_BOOKING_OVERRIDE
from portal.application.facility.recurring_override_mail_service import RecurringOverrideMailService
from portal.application.facility.results import RecurringOverrideNotification, RecurringOverrideNotificationItem, RoomDetailResult, TranslationItemResult
from portal.cli.datas.rbac_seed_data import resources
from portal.domain.facility.constants import BOOKING_PAYMENT_RESOURCE_CODE
from portal.domain.org.constants import FACILITY_DEACON_POSITION_CODE
from portal.libs.consts.permission import Resource
from portal.providers.template_render_provider import TemplateRenderProvider
from tests.fixtures.facility.stubs import StubRoomRepository
from tests.fixtures.org.stubs import StubPositionRepository


class StubMailSendPort:
    def __init__(self):
        self.calls: list[dict] = []

    async def send_html_mail(self, *, to_email: str, subject: str, body_html: str) -> None:
        self.calls.append({"to_email": to_email, "subject": subject, "body_html": body_html})


class StubMailUserRepository:
    def __init__(self, users: dict[UUID, UserSensitive]):
        self.users = users

    async def get_sensitive_by_id(self, user_id: UUID):
        return self.users.get(user_id)


class StubPermissionRepository:
    def __init__(self, emails: list[str] | None = None):
        self.emails = emails or []
        self.resource_codes: list[str] = []

    async def list_active_emails_for_resource_code(self, resource_code: str) -> list[str]:
        self.resource_codes.append(resource_code)
        return list(self.emails)


def _user(user_id: UUID, email: str, is_active: bool = True) -> UserSensitive:
    return UserSensitive(id=user_id, email=email, verified=True, is_active=is_active, is_admin=False)


def _notification(*, booker_id: UUID, facility_id: UUID, booking_id: UUID | None = None) -> RecurringOverrideNotification:
    rental_booking_id = booking_id or uuid4()
    return RecurringOverrideNotification(
        series_id=uuid4(),
        ministry_id=uuid4(),
        church_activity_name="Youth Fellowship",
        church_activity_name_zh="青年團契",
        actor_id=uuid4(),
        items=[
            RecurringOverrideNotificationItem(
                booking_id=rental_booking_id,
                booker_id=booker_id,
                occurrence_date=date(2026, 1, 13),
                facility_ids=[facility_id],
                church_activity_booking_id=uuid4(),
            )
        ],
    )


def _mail_service(
    mail_port: StubMailSendPort,
    user_stub: StubMailUserRepository,
    permission_stub: StubPermissionRepository,
    position_stub: StubPositionRepository,
    room_stub: StubRoomRepository,
    *,
    enabled: bool = True,
    override_recipients: list[str] | None = None,
) -> RecurringOverrideMailService:
    return RecurringOverrideMailService(
        mail_port,
        TemplateRenderProvider(),
        user_stub,
        permission_stub,
        position_stub,
        room_stub,
        facility_booking_base_url="http://localhost:5174",
        enabled=enabled,
        override_recipients=override_recipients,
    )


def test_booking_payment_resource_is_seeded_hidden_facility_child():
    item = next(resource for resource in resources if resource["code"] == BOOKING_PAYMENT_RESOURCE_CODE)
    assert item["name"] == "Booking Payment Confirmation"
    assert item["is_visible"] is False
    assert item["key"] == "FACILITY_BOOKING_PAYMENT"
    assert len(item["code"]) <= 32
    assert Resource.FACILITY_BOOKING_PAYMENT.value == BOOKING_PAYMENT_RESOURCE_CODE


@pytest.mark.asyncio
async def test_override_recipients_include_booker_operators_and_deacon_deduplicated():
    booker_id = uuid4()
    deacon_id = uuid4()
    operator_also_booker_email = "booker@efcnewlife.org"
    mail_port = StubMailSendPort()
    permission_stub = StubPermissionRepository(emails=[operator_also_booker_email, "operator@efcnewlife.org"])
    service = _mail_service(
        mail_port,
        StubMailUserRepository({booker_id: _user(booker_id, operator_also_booker_email), deacon_id: _user(deacon_id, "deacon@efcnewlife.org")}),
        permission_stub,
        StubPositionRepository(incumbents_by_code={FACILITY_DEACON_POSITION_CODE: deacon_id}),
        StubRoomRepository(),
    )
    notification = _notification(booker_id=booker_id, facility_id=uuid4())

    emails = await service.list_intended_recipient_emails(notification)

    assert emails == ["booker@efcnewlife.org", "operator@efcnewlife.org", "deacon@efcnewlife.org"]
    assert permission_stub.resource_codes == [BOOKING_PAYMENT_RESOURCE_CODE]


@pytest.mark.asyncio
async def test_override_recipients_skip_inactive_booker_and_missing_deacon():
    inactive_booker_id = uuid4()
    service = _mail_service(
        StubMailSendPort(),
        StubMailUserRepository({inactive_booker_id: _user(inactive_booker_id, "inactive@efcnewlife.org", is_active=False)}),
        StubPermissionRepository(emails=["operator@efcnewlife.org"]),
        StubPositionRepository(),
        StubRoomRepository(),
    )

    emails = await service.list_intended_recipient_emails(_notification(booker_id=inactive_booker_id, facility_id=uuid4()))

    assert emails == ["operator@efcnewlife.org"]


@pytest.mark.asyncio
async def test_notify_priority_override_sends_bilingual_mail_without_steward_contact():
    booker_id = uuid4()
    facility_id = uuid4()
    rental_booking_id = uuid4()
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
        mail_port,
        StubMailUserRepository({booker_id: _user(booker_id, "booker@efcnewlife.org")}),
        StubPermissionRepository(),
        StubPositionRepository(),
        StubRoomRepository(room_by_id={facility_id: room}),
    )

    await service.notify_priority_override(_notification(booker_id=booker_id, facility_id=facility_id, booking_id=rental_booking_id))

    assert len(mail_port.calls) == 1
    call = mail_port.calls[0]
    assert call["to_email"] == "booker@efcnewlife.org"
    assert call["subject"] == OVERRIDE_SUBJECT
    body_html = call["body_html"]
    english_marker_index = body_html.index("English")
    zh_marker_index = body_html.index("中文")
    divider_index = body_html.index("border-top: 1px solid #e9f3f5")
    assert english_marker_index < divider_index < zh_marker_index
    en_section = body_html[english_marker_index:divider_index]
    zh_section = body_html[zh_marker_index:]
    assert "Youth Fellowship" in en_section
    assert "January 13, 2026" in en_section
    assert "Gym A" in en_section
    assert "青年團契" in zh_section
    assert "2026年1月13日" in zh_section
    assert "體育館 A" in zh_section
    assert f"http://localhost:5174/my-bookings/{rental_booking_id}" in body_html
    assert "steward" not in body_html.lower()
    assert TEMPLATE_BOOKING_OVERRIDE.endswith("booking_override.html")


@pytest.mark.asyncio
async def test_notify_priority_override_redirects_to_override_recipients():
    booker_id = uuid4()
    mail_port = StubMailSendPort()
    service = _mail_service(
        mail_port,
        StubMailUserRepository({booker_id: _user(booker_id, "booker@efcnewlife.org")}),
        StubPermissionRepository(),
        StubPositionRepository(),
        StubRoomRepository(),
        override_recipients=["dev@local.test"],
    )

    await service.notify_priority_override(_notification(booker_id=booker_id, facility_id=uuid4()))

    assert mail_port.calls[0]["to_email"] == "dev@local.test"
    assert mail_port.calls[0]["subject"].startswith("[DEV -> booker@efcnewlife.org] ")


@pytest.mark.asyncio
async def test_notify_priority_override_skips_when_disabled():
    booker_id = uuid4()
    mail_port = StubMailSendPort()
    service = _mail_service(
        mail_port,
        StubMailUserRepository({booker_id: _user(booker_id, "booker@efcnewlife.org")}),
        StubPermissionRepository(),
        StubPositionRepository(),
        StubRoomRepository(),
        enabled=False,
    )

    await service.notify_priority_override(_notification(booker_id=booker_id, facility_id=uuid4()))

    assert mail_port.calls == []
