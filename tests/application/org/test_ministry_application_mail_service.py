"""
Tests for ministry application mail dispatch.
"""

from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest

from portal.application.auth.results import UserDetail, UserSensitive
from portal.application.org.ministry_application_mail_content import EN_LOCALE_ID, ZH_TW_LOCALE_ID
from portal.application.org.ministry_application_mail_service import MinistryApplicationMailService
from portal.application.org.results import MinistryDetailResult, MinistryMemberResult, TargetAudienceResult, TranslationItemResult
from portal.domain.org.constants import MinistryDecisionChannel, MinistryMemberRole, MinistryStatus
from portal.providers.template_render_provider import TemplateRenderProvider
from tests.fixtures.org.stubs import StubMinistryRepository, StubPositionRepository


class StubMailSendPort:
    def __init__(self):
        self.calls: list[dict] = []

    async def send_html_mail(self, *, to_email: str, subject: str, body_html: str) -> None:
        self.calls.append({"to_email": to_email, "subject": subject, "body_html": body_html})


class StubMailUserRepository:
    def __init__(self, users: dict[UUID, UserSensitive], profiles: dict[UUID, UserDetail] | None = None):
        self.users = users
        self.profiles = profiles or {}

    async def get_sensitive_by_id(self, user_id: UUID):
        return self.users.get(user_id)

    async def get_detail_by_id(self, user_id: UUID):
        return self.profiles.get(user_id)


def make_mail_service(
    mail_port: StubMailSendPort,
    ministry_stub: StubMinistryRepository,
    position_stub: StubPositionRepository,
    user_stub: StubMailUserRepository,
    *,
    enabled: bool = True,
    override_recipients: list[str] | None = None,
) -> MinistryApplicationMailService:
    return MinistryApplicationMailService(
        mail_port,
        TemplateRenderProvider(),
        ministry_stub,
        position_stub,
        user_stub,
        facility_booking_base_url="http://localhost:5174",
        enabled=enabled,
        override_recipients=override_recipients,
    )


@pytest.mark.asyncio
async def test_send_submit_notifications_sends_applicant_and_incumbent_emails():
    ministry_id = uuid4()
    owner_position_id = uuid4()
    applicant_user_id = uuid4()
    incumbent_user_id = uuid4()
    mail_port = StubMailSendPort()
    ministry_stub = StubMinistryRepository(
        ministry_by_id={
            ministry_id: MinistryDetailResult(
                id=ministry_id,
                name="Fallback",
                status=MinistryStatus.PENDING_APPROVAL.value,
                owner_position_id=owner_position_id,
                ministry_type_name="Sports",
                submitted_at=datetime(2026, 1, 15, 18, 30, tzinfo=timezone.utc),
                has_priority_booking=False,
                is_active=True,
                translations=[
                    TranslationItemResult(locale_id=EN_LOCALE_ID, name="Badminton Club"),
                    TranslationItemResult(locale_id=ZH_TW_LOCALE_ID, name="羽毛球社"),
                ],
                target_audiences=[TargetAudienceResult(id=uuid4(), code="adults", name="Adults")],
                members=[MinistryMemberResult(user_id=applicant_user_id, member_role=MinistryMemberRole.PRIMARY.value, display_name="Primary Steward")],
            )
        }
    )
    user_stub = StubMailUserRepository(
        users={
            applicant_user_id: UserSensitive(id=applicant_user_id, email="applicant@example.com", verified=True, is_active=True, is_admin=False),
            incumbent_user_id: UserSensitive(id=incumbent_user_id, email="incumbent@example.com", verified=True, is_active=True, is_admin=False),
        },
        profiles={applicant_user_id: UserDetail(id=applicant_user_id, email="applicant@example.com", preferred_name="Applicant Name")},
    )
    service = make_mail_service(mail_port, ministry_stub, StubPositionRepository(incumbents={owner_position_id: incumbent_user_id}), user_stub)

    await service.send_submit_notifications(ministry_id=ministry_id, owner_position_id=owner_position_id, applicant_user_id=applicant_user_id)

    assert len(mail_port.calls) == 2
    applicant_call = next(call for call in mail_port.calls if call["to_email"] == "applicant@example.com")
    incumbent_call = next(call for call in mail_port.calls if call["to_email"] == "incumbent@example.com")
    assert "Badminton Club" in applicant_call["body_html"]
    assert "羽毛球社" in applicant_call["body_html"]
    assert "/my-ministry" in applicant_call["body_html"]
    assert "New Life Facility Booking" in applicant_call["body_html"]
    assert f"/my-ministry/approvals/{ministry_id}" in incumbent_call["body_html"]
    assert "Applicant Name" in incumbent_call["body_html"]
    assert "Application summary" in incumbent_call["body_html"]
    assert "Sports" in incumbent_call["body_html"]


@pytest.mark.asyncio
async def test_send_submit_notifications_redirects_to_override_recipients():
    ministry_id = uuid4()
    owner_position_id = uuid4()
    applicant_user_id = uuid4()
    incumbent_user_id = uuid4()
    mail_port = StubMailSendPort()
    ministry_stub = StubMinistryRepository(
        ministry_by_id={
            ministry_id: MinistryDetailResult(
                id=ministry_id,
                name="Badminton",
                status=MinistryStatus.PENDING_APPROVAL.value,
                owner_position_id=owner_position_id,
                has_priority_booking=False,
                is_active=True,
            )
        }
    )
    user_stub = StubMailUserRepository(
        users={
            applicant_user_id: UserSensitive(id=applicant_user_id, email="applicant@example.com", verified=True, is_active=True, is_admin=False),
            incumbent_user_id: UserSensitive(id=incumbent_user_id, email="incumbent@example.com", verified=True, is_active=True, is_admin=False),
        }
    )
    service = make_mail_service(
        mail_port, ministry_stub, StubPositionRepository(incumbents={owner_position_id: incumbent_user_id}), user_stub, override_recipients=["dev@local.test"]
    )

    await service.send_submit_notifications(ministry_id=ministry_id, owner_position_id=owner_position_id, applicant_user_id=applicant_user_id)

    assert len(mail_port.calls) == 2
    assert all(call["to_email"] == "dev@local.test" for call in mail_port.calls)
    assert all(call["subject"].startswith("[DEV ->") for call in mail_port.calls)
    assert any("[DEV -> applicant@example.com]" in call["subject"] for call in mail_port.calls)
    assert any("[DEV -> incumbent@example.com]" in call["subject"] for call in mail_port.calls)


@pytest.mark.asyncio
async def test_send_submit_notifications_noop_when_disabled():
    mail_port = StubMailSendPort()
    service = make_mail_service(mail_port, StubMinistryRepository(), StubPositionRepository(), StubMailUserRepository(users={}), enabled=False)
    await service.send_submit_notifications(ministry_id=uuid4(), owner_position_id=uuid4(), applicant_user_id=uuid4())
    assert mail_port.calls == []


@pytest.mark.asyncio
async def test_send_decision_notification_incumbent_channel_sends_single_applicant_email():
    ministry_id = uuid4()
    owner_position_id = uuid4()
    applicant_user_id = uuid4()
    incumbent_user_id = uuid4()
    mail_port = StubMailSendPort()
    ministry_stub = StubMinistryRepository(
        ministry_by_id={
            ministry_id: MinistryDetailResult(
                id=ministry_id,
                name="Badminton",
                status=MinistryStatus.PENDING_APPROVAL.value,
                owner_position_id=owner_position_id,
                submitted_by_id=applicant_user_id,
                has_priority_booking=False,
                is_active=True,
                translations=[
                    TranslationItemResult(locale_id=EN_LOCALE_ID, name="Badminton Club"),
                    TranslationItemResult(locale_id=ZH_TW_LOCALE_ID, name="羽毛球社"),
                ],
            )
        }
    )
    user_stub = StubMailUserRepository(
        users={
            applicant_user_id: UserSensitive(id=applicant_user_id, email="applicant@example.com", verified=True, is_active=True, is_admin=False),
            incumbent_user_id: UserSensitive(id=incumbent_user_id, email="incumbent@example.com", verified=True, is_active=True, is_admin=False),
        }
    )
    service = make_mail_service(mail_port, ministry_stub, StubPositionRepository(incumbents={owner_position_id: incumbent_user_id}), user_stub)

    await service.send_decision_notification(
        ministry_id=ministry_id,
        applicant_user_id=applicant_user_id,
        approved=False,
        decision_channel=MinistryDecisionChannel.INCUMBENT,
        decided_by_user_id=incumbent_user_id,
        owner_position_id=owner_position_id,
        rejection_reason="Incomplete roster",
    )

    assert len(mail_port.calls) == 1
    assert mail_port.calls[0]["to_email"] == "applicant@example.com"
    assert "Declined" in mail_port.calls[0]["subject"]
    assert "was not approved" in mail_port.calls[0]["body_html"]
    assert "Incomplete roster" in mail_port.calls[0]["body_html"]
    assert "羽毛球社" in mail_port.calls[0]["body_html"]
    assert "未獲核准" in mail_port.calls[0]["body_html"]
    assert "on behalf of" not in mail_port.calls[0]["body_html"]


@pytest.mark.asyncio
async def test_send_decision_notification_staff_channel_sends_applicant_and_incumbent_emails():
    ministry_id = uuid4()
    owner_position_id = uuid4()
    applicant_user_id = uuid4()
    incumbent_user_id = uuid4()
    staff_user_id = uuid4()
    mail_port = StubMailSendPort()
    ministry_stub = StubMinistryRepository(
        ministry_by_id={
            ministry_id: MinistryDetailResult(
                id=ministry_id,
                name="Badminton",
                status=MinistryStatus.PENDING_APPROVAL.value,
                owner_position_id=owner_position_id,
                submitted_by_id=applicant_user_id,
                has_priority_booking=False,
                is_active=True,
                translations=[TranslationItemResult(locale_id=EN_LOCALE_ID, name="Badminton Club")],
            )
        }
    )
    user_stub = StubMailUserRepository(
        users={
            applicant_user_id: UserSensitive(id=applicant_user_id, email="applicant@example.com", verified=True, is_active=True, is_admin=False),
            incumbent_user_id: UserSensitive(id=incumbent_user_id, email="incumbent@example.com", verified=True, is_active=True, is_admin=False),
            staff_user_id: UserSensitive(id=staff_user_id, email="staff@example.com", verified=True, is_active=True, is_admin=True),
        },
        profiles={
            staff_user_id: UserDetail(id=staff_user_id, email="staff@example.com", preferred_name="Staff Member"),
            incumbent_user_id: UserDetail(id=incumbent_user_id, email="incumbent@example.com", preferred_name="Incumbent Leader"),
        },
    )
    service = make_mail_service(mail_port, ministry_stub, StubPositionRepository(incumbents={owner_position_id: incumbent_user_id}), user_stub)

    await service.send_decision_notification(
        ministry_id=ministry_id,
        applicant_user_id=applicant_user_id,
        approved=True,
        decision_channel=MinistryDecisionChannel.STAFF,
        decided_by_user_id=staff_user_id,
        owner_position_id=owner_position_id,
    )

    assert len(mail_port.calls) == 2
    applicant_call = next(call for call in mail_port.calls if call["to_email"] == "applicant@example.com")
    incumbent_call = next(call for call in mail_port.calls if call["to_email"] == "incumbent@example.com")
    assert "Staff Member" in applicant_call["body_html"]
    assert "Incumbent Leader" in applicant_call["body_html"]
    assert "on your behalf" in incumbent_call["body_html"]
    assert "Staff Member" in incumbent_call["body_html"]


@pytest.mark.asyncio
async def test_send_decision_notification_staff_channel_reject_includes_reason_and_incumbent_notification():
    ministry_id = uuid4()
    owner_position_id = uuid4()
    applicant_user_id = uuid4()
    incumbent_user_id = uuid4()
    staff_user_id = uuid4()
    mail_port = StubMailSendPort()
    ministry_stub = StubMinistryRepository(
        ministry_by_id={
            ministry_id: MinistryDetailResult(
                id=ministry_id,
                name="Badminton",
                status=MinistryStatus.PENDING_APPROVAL.value,
                owner_position_id=owner_position_id,
                submitted_by_id=applicant_user_id,
                has_priority_booking=False,
                is_active=True,
                translations=[TranslationItemResult(locale_id=EN_LOCALE_ID, name="Badminton Club")],
            )
        }
    )
    user_stub = StubMailUserRepository(
        users={
            applicant_user_id: UserSensitive(id=applicant_user_id, email="applicant@example.com", verified=True, is_active=True, is_admin=False),
            incumbent_user_id: UserSensitive(id=incumbent_user_id, email="incumbent@example.com", verified=True, is_active=True, is_admin=False),
            staff_user_id: UserSensitive(id=staff_user_id, email="staff@example.com", verified=True, is_active=True, is_admin=True),
        },
        profiles={
            staff_user_id: UserDetail(id=staff_user_id, email="staff@example.com", preferred_name="Staff Member"),
            incumbent_user_id: UserDetail(id=incumbent_user_id, email="incumbent@example.com", preferred_name="Incumbent Leader"),
        },
    )
    service = make_mail_service(mail_port, ministry_stub, StubPositionRepository(incumbents={owner_position_id: incumbent_user_id}), user_stub)

    await service.send_decision_notification(
        ministry_id=ministry_id,
        applicant_user_id=applicant_user_id,
        approved=False,
        decision_channel=MinistryDecisionChannel.STAFF,
        decided_by_user_id=staff_user_id,
        owner_position_id=owner_position_id,
        rejection_reason="Incomplete roster",
    )

    assert len(mail_port.calls) == 2
    applicant_call = next(call for call in mail_port.calls if call["to_email"] == "applicant@example.com")
    incumbent_call = next(call for call in mail_port.calls if call["to_email"] == "incumbent@example.com")
    assert "Incomplete roster" in applicant_call["body_html"]
    assert "Staff Member" in applicant_call["body_html"]
    assert "Incumbent Leader" in applicant_call["body_html"]
    assert "staff@example.com" not in applicant_call["body_html"]
    assert "Incomplete roster" in incumbent_call["body_html"]
    assert "No further action" in incumbent_call["body_html"]
