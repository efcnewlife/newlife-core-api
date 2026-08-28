"""
Tests for ministry application mail dispatch.
"""

from uuid import UUID, uuid4

import pytest

from portal.application.auth.results import UserDetail, UserSensitive
from portal.application.org.ministry_application_mail_content import EN_LOCALE_ID, ZH_TW_LOCALE_ID
from portal.application.org.ministry_application_mail_service import MinistryApplicationMailService
from portal.application.org.results import MinistryDetailResult, TranslationItemResult
from portal.domain.org.constants import MinistryStatus
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
        },
        profiles={applicant_user_id: UserDetail(id=applicant_user_id, email="applicant@example.com", preferred_name="Applicant Name")},
    )
    service = MinistryApplicationMailService(
        mail_port,
        ministry_stub,
        StubPositionRepository(incumbents={owner_position_id: incumbent_user_id}),
        user_stub,
        facility_booking_base_url="http://localhost:5174",
        enabled=True,
    )

    await service.send_submit_notifications(ministry_id=ministry_id, owner_position_id=owner_position_id, applicant_user_id=applicant_user_id)

    assert len(mail_port.calls) == 2
    applicant_call = next(call for call in mail_port.calls if call["to_email"] == "applicant@example.com")
    incumbent_call = next(call for call in mail_port.calls if call["to_email"] == "incumbent@example.com")
    assert "Badminton Club" in applicant_call["body_html"]
    assert "羽毛球社" in applicant_call["body_html"]
    assert "/my-ministry" in applicant_call["body_html"]
    assert f"/my-ministry/approvals/{ministry_id}" in incumbent_call["body_html"]
    assert "Applicant Name" in incumbent_call["body_html"]


@pytest.mark.asyncio
async def test_send_submit_notifications_noop_when_disabled():
    mail_port = StubMailSendPort()
    service = MinistryApplicationMailService(
        mail_port,
        StubMinistryRepository(),
        StubPositionRepository(),
        StubMailUserRepository(users={}),
        facility_booking_base_url="http://localhost:5174",
        enabled=False,
    )
    await service.send_submit_notifications(ministry_id=uuid4(), owner_position_id=uuid4(), applicant_user_id=uuid4())
    assert mail_port.calls == []
