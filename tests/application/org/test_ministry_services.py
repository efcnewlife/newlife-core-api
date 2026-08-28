"""
Org application unit tests.
"""

from datetime import time
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from portal.application.auth.results import UserSensitive
from portal.application.org.commands import (
    ApproveMinistryCommand,
    CreateMinistryCommand,
    MinistryApplicationCommand,
    MinistryMemberEntryCommand,
    MinistryScheduleCommand,
    OrgTranslationCommand,
    OrgUserSearchCommand,
    PagesQueryCommand,
    RejectMinistryCommand,
    ReplaceMinistryMembersCommand,
    StewardDirectoryQueryCommand,
    SubmitMinistryCommand,
    UpdateRejectedMinistryApplicationCommand,
)
from portal.application.org.ministry_application_mail_content import EN_LOCALE_ID
from portal.application.org.ministry_application_mail_service import MinistryApplicationMailService
from portal.application.org.ministry_approval_service import MinistryApprovalService
from portal.application.org.ministry_schedule import validate_ministry_schedules
from portal.application.org.ministry_service import MinistryService
from portal.application.org.org_user_search_service import OrgUserSearchService
from portal.application.org.results import (
    MinistryDetailResult,
    MinistryListItemResult,
    MinistryMemberResult,
    OrgUserSearchItemResult,
    TargetAudienceResult,
    TranslationItemResult,
)
from portal.application.org.steward_directory_query import matches_steward_directory_q
from portal.application.org.target_audience_validation import validate_target_audience_ids
from portal.domain.facility.days_of_week_mask import days_to_mask, mask_to_days
from portal.domain.org.catalog_codes import TARGET_AUDIENCE_ADULTS, TARGET_AUDIENCE_ALL_AGES
from portal.domain.org.constants import MinistryDecisionChannel, MinistryMemberRole, MinistryStatus
from portal.exceptions.responses import BadRequestException, ForbiddenException, NotFoundException
from portal.libs.contexts.user_context import UserContext
from portal.providers.template_render_provider import TemplateRenderProvider
from tests.application.org.test_ministry_application_mail_service import StubMailSendPort, StubMailUserRepository, make_mail_service
from tests.fixtures.org.stubs import (
    StubMinistryRepository,
    StubMinistryTypeRepository,
    StubPositionRepository,
    StubStewardDirectoryRow,
    StubTargetAudienceRepository,
    StubUserRepository,
)


def make_service(
    ministry_stub: StubMinistryRepository | None = None,
    type_stub: StubMinistryTypeRepository | None = None,
    audience_stub: StubTargetAudienceRepository | None = None,
) -> MinistryService:
    return MinistryService(
        ministry_stub or StubMinistryRepository(), type_stub or StubMinistryTypeRepository(), audience_stub or StubTargetAudienceRepository()
    )


def make_approval_service(
    ministry_stub: StubMinistryRepository,
    *,
    type_stub: StubMinistryTypeRepository | None = None,
    audience_stub: StubTargetAudienceRepository | None = None,
    position_stub: StubPositionRepository | None = None,
    mail_service: MinistryApplicationMailService | None = None,
) -> MinistryApprovalService:
    return MinistryApprovalService(
        ministry_stub,
        make_service(ministry_stub, type_stub=type_stub, audience_stub=audience_stub),
        position_stub or StubPositionRepository(),
        ministry_application_mail_service=mail_service,
    )


@pytest.mark.asyncio
async def test_create_ministry_requires_translations():
    with pytest.raises(ValidationError):
        CreateMinistryCommand()


@pytest.mark.asyncio
async def test_submit_ministry_requires_owner_position():
    ministry_id = uuid4()
    stub = StubMinistryRepository(
        ministry_by_id={
            ministry_id: MinistryDetailResult(id=ministry_id, name="Youth", status=MinistryStatus.DRAFT.value, has_priority_booking=False, is_active=True)
        }
    )
    approval_service = make_approval_service(stub)
    with pytest.raises(BadRequestException, match="owner_position_id"):
        await approval_service.submit_ministry(ministry_id, SubmitMinistryCommand())


@pytest.mark.asyncio
async def test_validate_members_for_submit_requires_primary_and_secondary():
    ministry_id = uuid4()
    stub = StubMinistryRepository(
        ministry_by_id={
            ministry_id: MinistryDetailResult(id=ministry_id, name="Youth", status=MinistryStatus.DRAFT.value, has_priority_booking=False, is_active=True)
        },
        members_by_ministry={ministry_id: [MinistryMemberResult(user_id=uuid4(), member_role=MinistryMemberRole.PRIMARY.value)]},
    )
    service = make_service(stub)
    with pytest.raises(BadRequestException, match="secondary") as exc_info:
        await service.validate_members_for_submit(ministry_id)
    assert exc_info.value.error_code == "ORG_MINISTRY_SECONDARY_REQUIRED"


@pytest.mark.asyncio
async def test_validate_members_for_submit_requires_primary():
    ministry_id = uuid4()
    stub = StubMinistryRepository(
        ministry_by_id={
            ministry_id: MinistryDetailResult(id=ministry_id, name="Youth", status=MinistryStatus.DRAFT.value, has_priority_booking=False, is_active=True)
        },
        members_by_ministry={ministry_id: [MinistryMemberResult(user_id=uuid4(), member_role=MinistryMemberRole.SECONDARY.value)]},
    )
    service = make_service(stub)
    with pytest.raises(BadRequestException, match="primary") as exc_info:
        await service.validate_members_for_submit(ministry_id)
    assert exc_info.value.error_code == "ORG_MINISTRY_PRIMARY_REQUIRED"


@pytest.mark.asyncio
async def test_submit_ministry_not_found_error_code():
    ministry_id = uuid4()
    stub = StubMinistryRepository(ministry_by_id={})
    approval_service = make_approval_service(stub)
    with pytest.raises(NotFoundException) as exc_info:
        await approval_service.submit_ministry(ministry_id, SubmitMinistryCommand())
    assert exc_info.value.error_code == "ORG_MINISTRY_NOT_FOUND"
    assert exc_info.value.context == {"ministry_id": str(ministry_id)}


@pytest.mark.asyncio
async def test_replace_members_success():
    ministry_id = uuid4()
    primary_id = uuid4()
    secondary_id = uuid4()
    stub = StubMinistryRepository(
        ministry_by_id={
            ministry_id: MinistryDetailResult(id=ministry_id, name="Youth", status=MinistryStatus.DRAFT.value, has_priority_booking=False, is_active=True)
        }
    )
    service = make_service(stub)
    await service.replace_members(
        ministry_id,
        ReplaceMinistryMembersCommand(
            members=[
                MinistryMemberEntryCommand(user_id=primary_id, member_role=MinistryMemberRole.PRIMARY, contact_email="primary@example.com"),
                MinistryMemberEntryCommand(user_id=secondary_id, member_role=MinistryMemberRole.SECONDARY),
            ]
        ),
    )
    assert len(stub.replace_members_calls) == 1
    assert stub.replace_members_calls[0]["members"][0]["contact_email"] == "primary@example.com"


@pytest.mark.asyncio
async def test_create_ministry_with_translation():
    stub = StubMinistryRepository()
    service = make_service(stub)
    locale_id = uuid4()
    result = await service.create_ministry(
        CreateMinistryCommand(translations=[OrgTranslationCommand(locale_id=locale_id, name="Youth Ministry", schedule_note="Summer off")])
    )
    assert result.id is not None
    assert len(stub.insert_calls) == 1
    assert stub.insert_calls[0]["ministry_type_id"] is not None
    assert stub.upsert_translation_calls
    assert stub.upsert_translation_calls[0][0]["schedule_note"] == "Summer off"


@pytest.mark.asyncio
async def test_create_ministry_persists_schedules_and_target_audiences():
    stub = StubMinistryRepository()
    adults_id = uuid4()
    audience_stub = StubTargetAudienceRepository({adults_id: TargetAudienceResult(id=adults_id, code=TARGET_AUDIENCE_ADULTS)})
    service = make_service(stub, audience_stub=audience_stub)
    locale_id = uuid4()
    ministry_type_id = uuid4()
    type_stub = StubMinistryTypeRepository(default_type_id=ministry_type_id)
    service = make_service(stub, type_stub=type_stub, audience_stub=audience_stub)
    await service.create_ministry(
        CreateMinistryCommand(
            ministry_type_id=ministry_type_id,
            target_audience_ids=[adults_id],
            schedules=[MinistryScheduleCommand(days_of_week=[0, 6], start_time=time(13, 30), end_time=time(16, 30))],
            translations=[OrgTranslationCommand(locale_id=locale_id, name="Badminton")],
        )
    )
    assert stub.upsert_schedules_calls
    assert stub.upsert_schedules_calls[0]["rows"][0]["days_of_week_mask"] == days_to_mask([0, 6])
    assert stub.upsert_target_audiences_calls[0]["audience_ids"] == [adults_id]


def test_schedule_mask_round_trip():
    assert mask_to_days(days_to_mask([0, 2, 4])) == [0, 2, 4]


def test_validate_time_tba_schedule_requires_anchor():
    with pytest.raises(BadRequestException):
        validate_ministry_schedules([MinistryScheduleCommand()])


def test_all_ages_target_audience_is_exclusive():
    adults_id = uuid4()
    all_ages_id = uuid4()
    with pytest.raises(BadRequestException) as exc_info:
        validate_target_audience_ids(
            [all_ages_id, adults_id],
            [TargetAudienceResult(id=all_ages_id, code=TARGET_AUDIENCE_ALL_AGES), TargetAudienceResult(id=adults_id, code=TARGET_AUDIENCE_ADULTS)],
        )
    assert exc_info.value.error_code == "ORG_MINISTRY_INVALID_TARGET_AUDIENCES"


def _directory_fixture() -> tuple[UUID, UUID, UUID, StubMinistryRepository]:
    youth_id = uuid4()
    alpha_id = uuid4()
    empty_id = uuid4()
    stub = StubMinistryRepository(
        directory_rows=[
            StubStewardDirectoryRow(
                id=youth_id,
                name="Youth",
                status=MinistryStatus.DRAFT.value,
                stewards=[{"email": "jane.login@example.com", "display_name": "Jane Steward", "contact_email": "jane.public@church.org"}],
            ),
            StubStewardDirectoryRow(id=alpha_id, name="Alpha 2026", status=MinistryStatus.ACTIVE.value, stewards=[]),
            StubStewardDirectoryRow(id=empty_id, name="Choir", status=MinistryStatus.INACTIVE.value, stewards=[]),
            StubStewardDirectoryRow(
                id=uuid4(),
                name="Deleted Group",
                status=MinistryStatus.ACTIVE.value,
                is_deleted=True,
                stewards=[{"email": "gone@example.com", "display_name": "Gone", "contact_email": None}],
            ),
        ]
    )
    return youth_id, alpha_id, empty_id, stub


def test_matches_steward_directory_q_is_case_insensitive_partial():
    assert matches_steward_directory_q(
        "JANE",
        translation_names=["Youth"],
        steward_login_emails=["jane.login@example.com"],
        steward_display_names=["Jane Steward"],
        steward_contact_emails=["jane.public@church.org"],
    )
    assert matches_steward_directory_q(
        "login",
        translation_names=["Youth"],
        steward_login_emails=["jane.login@example.com"],
        steward_display_names=["Jane Steward"],
        steward_contact_emails=["jane.public@church.org"],
    )
    assert matches_steward_directory_q(
        "church.org",
        translation_names=["Youth"],
        steward_login_emails=["jane.login@example.com"],
        steward_display_names=["Jane Steward"],
        steward_contact_emails=["jane.public@church.org"],
    )
    assert not matches_steward_directory_q("Jane", translation_names=["Choir"], steward_login_emails=[], steward_display_names=[], steward_contact_emails=[])


@pytest.mark.asyncio
async def test_steward_directory_empty_q_includes_empty_rosters_and_omits_deleted():
    youth_id, alpha_id, empty_id, stub = _directory_fixture()
    result = await make_service(stub).get_steward_directory(StewardDirectoryQueryCommand())
    ids = {item.id for item in result.items}
    assert ids == {youth_id, alpha_id, empty_id}
    assert result.total == 3
    assert all("members" not in item.model_dump() for item in result.items)


@pytest.mark.asyncio
async def test_steward_directory_filters_status():
    _, alpha_id, _, stub = _directory_fixture()
    result = await make_service(stub).get_steward_directory(StewardDirectoryQueryCommand(status=MinistryStatus.ACTIVE))
    assert [item.id for item in result.items] == [alpha_id]


@pytest.mark.asyncio
async def test_steward_directory_q_matches_ministry_name_and_steward_identity():
    youth_id, alpha_id, _, stub = _directory_fixture()
    service = make_service(stub)
    by_name = await service.get_steward_directory(StewardDirectoryQueryCommand(q="alpha"))
    assert [item.id for item in by_name.items] == [alpha_id]
    by_person = await service.get_steward_directory(StewardDirectoryQueryCommand(q="Jane"))
    assert [item.id for item in by_person.items] == [youth_id]
    mixed = await service.get_steward_directory(StewardDirectoryQueryCommand(q="a"))
    assert {item.id for item in mixed.items} == {youth_id, alpha_id}


@pytest.mark.asyncio
async def test_steward_directory_person_q_excludes_empty_roster():
    youth_id, _, empty_id, stub = _directory_fixture()
    service = make_service(stub)
    by_name = await service.get_steward_directory(StewardDirectoryQueryCommand(q="Choir"))
    assert [item.id for item in by_name.items] == [empty_id]
    by_person = await service.get_steward_directory(StewardDirectoryQueryCommand(q="Jane"))
    assert [item.id for item in by_person.items] == [youth_id]
    person_miss = await service.get_steward_directory(StewardDirectoryQueryCommand(q="Nobody"))
    assert person_miss.items == []


@pytest.mark.asyncio
async def test_steward_directory_paginates():
    _, _, _, stub = _directory_fixture()
    result = await make_service(stub).get_steward_directory(StewardDirectoryQueryCommand(page=0, page_size=1))
    assert result.page == 0
    assert result.page_size == 1
    assert result.total == 3
    assert len(result.items) == 1


@pytest.mark.asyncio
async def test_steward_directory_orders_by_name():
    youth_id, alpha_id, empty_id, stub = _directory_fixture()
    result = await make_service(stub).get_steward_directory(StewardDirectoryQueryCommand(order_by="name", descending=False, page_size=10))
    assert [item.id for item in result.items] == [alpha_id, empty_id, youth_id]


@pytest.mark.asyncio
async def test_ministry_pages_keyword_matches_name_not_steward():
    youth_id, _, _, stub = _directory_fixture()
    service = make_service(stub)
    by_name = await service.get_ministry_pages(PagesQueryCommand(keyword="Youth"))
    assert [item.id for item in by_name.items] == [youth_id]
    by_steward = await service.get_ministry_pages(PagesQueryCommand(keyword="Jane"))
    assert by_steward.items == []


@pytest.mark.asyncio
async def test_replace_members_rejects_missing_secondary():
    ministry_id = uuid4()
    stub = StubMinistryRepository(
        ministry_by_id={
            ministry_id: MinistryDetailResult(id=ministry_id, name="Youth", status=MinistryStatus.DRAFT.value, has_priority_booking=False, is_active=True)
        }
    )
    service = make_service(stub)
    with pytest.raises(BadRequestException, match="secondary"):
        await service.replace_members(
            ministry_id, ReplaceMinistryMembersCommand(members=[MinistryMemberEntryCommand(user_id=uuid4(), member_role=MinistryMemberRole.PRIMARY)])
        )
    assert stub.replace_members_calls == []


@pytest.mark.asyncio
async def test_submit_ministry_requires_owner_position_incumbent():
    ministry_id = uuid4()
    owner_position_id = uuid4()
    stub = StubMinistryRepository(
        ministry_by_id={
            ministry_id: MinistryDetailResult(
                id=ministry_id, name="Youth", status=MinistryStatus.DRAFT.value, owner_position_id=owner_position_id, has_priority_booking=False, is_active=True
            )
        },
        members_by_ministry={
            ministry_id: [
                MinistryMemberResult(user_id=uuid4(), member_role=MinistryMemberRole.PRIMARY.value),
                MinistryMemberResult(user_id=uuid4(), member_role=MinistryMemberRole.SECONDARY.value),
            ]
        },
    )
    approval_service = make_approval_service(stub, position_stub=StubPositionRepository(incumbents={}))
    with pytest.raises(BadRequestException, match="incumbent") as exc_info:
        await approval_service.submit_ministry(ministry_id, SubmitMinistryCommand())
    assert exc_info.value.error_code == "ORG_POSITION_NO_INCUMBENT"


@pytest.mark.asyncio
async def test_create_application_persists_type_and_target_audiences():
    owner_position_id = uuid4()
    ministry_type_id = uuid4()
    adults_id = uuid4()
    primary_id = uuid4()
    secondary_id = uuid4()
    locale_id = uuid4()
    stub = StubMinistryRepository()
    audience_stub = StubTargetAudienceRepository({adults_id: TargetAudienceResult(id=adults_id, code=TARGET_AUDIENCE_ADULTS)})
    type_stub = StubMinistryTypeRepository(default_type_id=ministry_type_id)
    position_stub = StubPositionRepository(incumbents={owner_position_id: uuid4()})
    approval_service = make_approval_service(stub, type_stub=type_stub, audience_stub=audience_stub, position_stub=position_stub)
    result = await approval_service.create_application(
        MinistryApplicationCommand(
            owner_position_id=owner_position_id,
            ministry_type_id=ministry_type_id,
            target_audience_ids=[adults_id],
            translations=[OrgTranslationCommand(locale_id=locale_id, name="Badminton")],
            members=[
                MinistryMemberEntryCommand(user_id=primary_id, member_role=MinistryMemberRole.PRIMARY),
                MinistryMemberEntryCommand(user_id=secondary_id, member_role=MinistryMemberRole.SECONDARY),
            ],
        )
    )
    assert result.id is not None
    assert stub.insert_calls[0]["ministry_type_id"] == ministry_type_id
    assert stub.upsert_target_audiences_calls[0]["audience_ids"] == [adults_id]
    assert stub.update_calls[-1]["values"]["status"] == MinistryStatus.PENDING_APPROVAL.value


@pytest.mark.asyncio
async def test_create_application_rejects_invalid_target_audiences():
    owner_position_id = uuid4()
    invalid_audience_id = uuid4()
    locale_id = uuid4()
    stub = StubMinistryRepository()
    audience_stub = StubTargetAudienceRepository({})
    position_stub = StubPositionRepository(incumbents={owner_position_id: uuid4()})
    approval_service = make_approval_service(stub, audience_stub=audience_stub, position_stub=position_stub)
    with pytest.raises(BadRequestException, match="target_audience") as exc_info:
        await approval_service.create_application(
            MinistryApplicationCommand(
                owner_position_id=owner_position_id,
                target_audience_ids=[invalid_audience_id],
                translations=[OrgTranslationCommand(locale_id=locale_id, name="Badminton")],
                members=[
                    MinistryMemberEntryCommand(user_id=uuid4(), member_role=MinistryMemberRole.PRIMARY),
                    MinistryMemberEntryCommand(user_id=uuid4(), member_role=MinistryMemberRole.SECONDARY),
                ],
            )
        )
    assert exc_info.value.error_code == "ORG_MINISTRY_INVALID_TARGET_AUDIENCES"
    assert stub.insert_calls == []


@pytest.mark.asyncio
async def test_create_application_requires_secondary_member():
    owner_position_id = uuid4()
    locale_id = uuid4()
    stub = StubMinistryRepository()
    position_stub = StubPositionRepository(incumbents={owner_position_id: uuid4()})
    approval_service = make_approval_service(stub, position_stub=position_stub)
    with pytest.raises(BadRequestException, match="secondary") as exc_info:
        await approval_service.create_application(
            MinistryApplicationCommand(
                owner_position_id=owner_position_id,
                translations=[OrgTranslationCommand(locale_id=locale_id, name="Badminton")],
                members=[MinistryMemberEntryCommand(user_id=uuid4(), member_role=MinistryMemberRole.PRIMARY)],
            )
        )
    assert exc_info.value.error_code == "ORG_MINISTRY_SECONDARY_REQUIRED"


@pytest.mark.asyncio
async def test_create_application_rejects_vacant_owner_position():
    owner_position_id = uuid4()
    locale_id = uuid4()
    stub = StubMinistryRepository()
    position_stub = StubPositionRepository(incumbents={})
    approval_service = make_approval_service(stub, position_stub=position_stub)
    with pytest.raises(BadRequestException, match="incumbent") as exc_info:
        await approval_service.create_application(
            MinistryApplicationCommand(
                owner_position_id=owner_position_id,
                translations=[OrgTranslationCommand(locale_id=locale_id, name="Badminton")],
                members=[
                    MinistryMemberEntryCommand(user_id=uuid4(), member_role=MinistryMemberRole.PRIMARY),
                    MinistryMemberEntryCommand(user_id=uuid4(), member_role=MinistryMemberRole.SECONDARY),
                ],
            )
        )
    assert exc_info.value.error_code == "ORG_POSITION_NO_INCUMBENT"
    assert stub.insert_calls == []


@pytest.mark.asyncio
async def test_submit_ministry_dispatches_submit_mail_notifications():
    ministry_id = uuid4()
    owner_position_id = uuid4()
    applicant_user_id = uuid4()
    incumbent_user_id = uuid4()
    stub = StubMinistryRepository(
        ministry_by_id={
            ministry_id: MinistryDetailResult(
                id=ministry_id,
                name="Badminton",
                status=MinistryStatus.DRAFT.value,
                owner_position_id=owner_position_id,
                has_priority_booking=False,
                is_active=True,
                translations=[TranslationItemResult(locale_id=EN_LOCALE_ID, name="Badminton Club")],
            )
        },
        members_by_ministry={
            ministry_id: [
                MinistryMemberResult(user_id=uuid4(), member_role=MinistryMemberRole.PRIMARY.value),
                MinistryMemberResult(user_id=uuid4(), member_role=MinistryMemberRole.SECONDARY.value),
            ]
        },
    )
    mail_port = StubMailSendPort()
    mail_service = make_mail_service(
        mail_port,
        stub,
        StubPositionRepository(incumbents={owner_position_id: incumbent_user_id}),
        StubMailUserRepository(
            users={
                applicant_user_id: UserSensitive(id=applicant_user_id, email="applicant@example.com", verified=True, is_active=True, is_admin=False),
                incumbent_user_id: UserSensitive(id=incumbent_user_id, email="incumbent@example.com", verified=True, is_active=True, is_admin=False),
            }
        ),
    )
    approval_service = make_approval_service(
        stub, position_stub=StubPositionRepository(incumbents={owner_position_id: incumbent_user_id}), mail_service=mail_service
    )
    approval_service._user_ctx = UserContext(user_id=applicant_user_id, email="applicant@example.com", is_admin=False, is_superuser=False)

    await approval_service.submit_ministry(ministry_id, SubmitMinistryCommand())

    assert len(mail_port.calls) == 2
    assert {call["to_email"] for call in mail_port.calls} == {"applicant@example.com", "incumbent@example.com"}


@pytest.mark.asyncio
async def test_org_user_search_requires_minimum_query_length():
    service = OrgUserSearchService(StubUserRepository())
    with pytest.raises(BadRequestException, match="at least 2"):
        await service.search_users(OrgUserSearchCommand(q="a"))


@pytest.mark.asyncio
async def test_org_user_search_excludes_requesting_user(monkeypatch):
    current_user_id = uuid4()
    monkeypatch.setattr(
        "portal.application.org.org_user_search_service.get_user_context",
        lambda: UserContext(user_id=current_user_id, email="me@example.com", is_admin=False, is_superuser=False),
    )
    repo = StubUserRepository()
    service = OrgUserSearchService(repo)
    await service.search_users(OrgUserSearchCommand(q="jane"))
    assert repo.last_search is not None
    assert repo.last_search["exclude_user_id"] == current_user_id
    assert repo.last_search["limit"] == 20


@pytest.mark.asyncio
async def test_org_user_search_returns_active_users():
    user_id = uuid4()
    repo = StubUserRepository([OrgUserSearchItemResult(id=user_id, email="jane@example.com", display_name="Jane Steward")])
    service = OrgUserSearchService(repo)
    result = await service.search_users(OrgUserSearchCommand(q="jane"))
    assert len(result.items) == 1
    assert result.items[0].email == "jane@example.com"


def _pending_ministry(*, ministry_id, owner_position_id, submitted_by_id, status=MinistryStatus.PENDING_APPROVAL.value) -> MinistryDetailResult:
    return MinistryDetailResult(
        id=ministry_id,
        name="Badminton",
        status=status,
        owner_position_id=owner_position_id,
        submitted_by_id=submitted_by_id,
        has_priority_booking=False,
        is_active=True,
        translations=[TranslationItemResult(locale_id=EN_LOCALE_ID, name="Badminton Club")],
    )


@pytest.mark.asyncio
async def test_approve_ministry_as_incumbent_allows_self_approve():
    ministry_id = uuid4()
    owner_position_id = uuid4()
    incumbent_user_id = uuid4()
    ministry = _pending_ministry(ministry_id=ministry_id, owner_position_id=owner_position_id, submitted_by_id=incumbent_user_id)
    stub = StubMinistryRepository(ministry_by_id={ministry_id: ministry})
    approval_service = make_approval_service(stub, position_stub=StubPositionRepository(incumbents={owner_position_id: incumbent_user_id}))
    approval_service._user_ctx = UserContext(user_id=incumbent_user_id, email="incumbent@example.com", is_admin=False, is_superuser=False)

    await approval_service.approve_ministry_as_incumbent(ministry_id, ApproveMinistryCommand())

    assert stub.update_calls[-1]["values"]["status"] == MinistryStatus.ACTIVE.value
    assert stub.update_approval_calls[-1]["status"] == "approved"


@pytest.mark.asyncio
async def test_approve_ministry_as_incumbent_forbidden_for_non_incumbent():
    ministry_id = uuid4()
    owner_position_id = uuid4()
    other_user_id = uuid4()
    ministry = _pending_ministry(ministry_id=ministry_id, owner_position_id=owner_position_id, submitted_by_id=uuid4())
    stub = StubMinistryRepository(ministry_by_id={ministry_id: ministry})
    approval_service = make_approval_service(stub, position_stub=StubPositionRepository(incumbents={owner_position_id: uuid4()}))
    approval_service._user_ctx = UserContext(user_id=other_user_id, email="other@example.com", is_admin=False, is_superuser=False)

    with pytest.raises(ForbiddenException) as exc_info:
        await approval_service.approve_ministry_as_incumbent(ministry_id, ApproveMinistryCommand())
    assert exc_info.value.error_code == "ORG_MINISTRY_APPROVAL_FORBIDDEN"
    assert stub.update_approval_calls == []


@pytest.mark.asyncio
async def test_reject_ministry_as_incumbent_requires_reason():
    ministry_id = uuid4()
    owner_position_id = uuid4()
    incumbent_user_id = uuid4()
    ministry = _pending_ministry(ministry_id=ministry_id, owner_position_id=owner_position_id, submitted_by_id=uuid4())
    stub = StubMinistryRepository(ministry_by_id={ministry_id: ministry})
    approval_service = make_approval_service(stub, position_stub=StubPositionRepository(incumbents={owner_position_id: incumbent_user_id}))
    approval_service._user_ctx = UserContext(user_id=incumbent_user_id, email="incumbent@example.com", is_admin=False, is_superuser=False)

    await approval_service.reject_ministry_as_incumbent(ministry_id, RejectMinistryCommand(rejection_reason="Incomplete roster"))

    assert stub.update_calls[-1]["values"]["status"] == MinistryStatus.REJECTED.value
    assert stub.update_calls[-1]["values"]["rejection_reason"] == "Incomplete roster"


@pytest.mark.asyncio
async def test_get_approval_detail_allows_steward_access():
    ministry_id = uuid4()
    steward_user_id = uuid4()
    ministry = _pending_ministry(ministry_id=ministry_id, owner_position_id=uuid4(), submitted_by_id=uuid4())
    stub = StubMinistryRepository(
        ministry_by_id={ministry_id: ministry},
        members_by_ministry={ministry_id: [MinistryMemberResult(user_id=steward_user_id, member_role=MinistryMemberRole.SECONDARY.value)]},
    )
    approval_service = make_approval_service(stub)
    approval_service._user_ctx = UserContext(user_id=steward_user_id, email="steward@example.com", is_admin=False, is_superuser=False)

    result = await approval_service.get_approval_detail(ministry_id)
    assert result.id == ministry_id


@pytest.mark.asyncio
async def test_get_approval_detail_forbidden_without_access():
    ministry_id = uuid4()
    ministry = _pending_ministry(ministry_id=ministry_id, owner_position_id=uuid4(), submitted_by_id=uuid4())
    stub = StubMinistryRepository(ministry_by_id={ministry_id: ministry})
    approval_service = make_approval_service(stub)
    approval_service._user_ctx = UserContext(user_id=uuid4(), email="stranger@example.com", is_admin=False, is_superuser=False)

    with pytest.raises(ForbiddenException) as exc_info:
        await approval_service.get_approval_detail(ministry_id)
    assert exc_info.value.error_code == "ORG_MINISTRY_ACCESS_FORBIDDEN"


@pytest.mark.asyncio
async def test_list_pending_for_incumbent_filters_by_incumbent():
    incumbent_user_id = uuid4()
    owner_position_id = uuid4()
    ministry_id = uuid4()

    class PendingStub(StubMinistryRepository):
        async def fetch_pending_for_incumbent(self, user_id, locale_id):
            if user_id == incumbent_user_id:
                return [
                    MinistryListItemResult(
                        id=ministry_id, name="Badminton", status=MinistryStatus.PENDING_APPROVAL.value, has_priority_booking=False, is_active=True
                    )
                ]
            return []

    stub = PendingStub()
    approval_service = make_approval_service(stub, position_stub=StubPositionRepository(incumbents={owner_position_id: incumbent_user_id}))
    approval_service._user_ctx = UserContext(user_id=incumbent_user_id, email="incumbent@example.com", is_admin=False, is_superuser=False)

    result = await approval_service.list_pending_for_incumbent()
    assert len(result.items) == 1
    assert result.items[0].id == ministry_id


@pytest.mark.asyncio
async def test_update_rejected_application_locks_owner_position():
    ministry_id = uuid4()
    applicant_user_id = uuid4()
    owner_position_id = uuid4()
    secondary_id = uuid4()
    locale_id = uuid4()
    ministry = _pending_ministry(
        ministry_id=ministry_id, owner_position_id=owner_position_id, submitted_by_id=applicant_user_id, status=MinistryStatus.REJECTED.value
    )
    stub = StubMinistryRepository(
        ministry_by_id={ministry_id: ministry},
        members_by_ministry={
            ministry_id: [
                MinistryMemberResult(user_id=applicant_user_id, member_role=MinistryMemberRole.PRIMARY.value),
                MinistryMemberResult(user_id=secondary_id, member_role=MinistryMemberRole.SECONDARY.value),
            ]
        },
    )
    approval_service = make_approval_service(stub)
    approval_service._user_ctx = UserContext(user_id=applicant_user_id, email="applicant@example.com", is_admin=False, is_superuser=False)

    new_secondary_id = uuid4()
    await approval_service.update_rejected_application(
        ministry_id,
        UpdateRejectedMinistryApplicationCommand(
            translations=[OrgTranslationCommand(locale_id=locale_id, name="Updated Name")],
            members=[
                MinistryMemberEntryCommand(user_id=applicant_user_id, member_role=MinistryMemberRole.PRIMARY),
                MinistryMemberEntryCommand(user_id=new_secondary_id, member_role=MinistryMemberRole.SECONDARY),
            ],
        ),
    )

    assert stub.upsert_translation_calls
    assert stub.replace_members_calls
    assert stub.update_calls[-1]["values"].get("owner_position_id") is None


@pytest.mark.asyncio
async def test_resubmit_rejected_application_returns_to_pending_approval():
    ministry_id = uuid4()
    applicant_user_id = uuid4()
    owner_position_id = uuid4()
    ministry = _pending_ministry(
        ministry_id=ministry_id, owner_position_id=owner_position_id, submitted_by_id=applicant_user_id, status=MinistryStatus.REJECTED.value
    )
    stub = StubMinistryRepository(
        ministry_by_id={ministry_id: ministry},
        members_by_ministry={
            ministry_id: [
                MinistryMemberResult(user_id=applicant_user_id, member_role=MinistryMemberRole.PRIMARY.value),
                MinistryMemberResult(user_id=uuid4(), member_role=MinistryMemberRole.SECONDARY.value),
            ]
        },
    )
    approval_service = make_approval_service(stub, position_stub=StubPositionRepository(incumbents={owner_position_id: uuid4()}))
    approval_service._user_ctx = UserContext(user_id=applicant_user_id, email="applicant@example.com", is_admin=False, is_superuser=False)

    await approval_service.resubmit_ministry(ministry_id)

    assert stub.update_calls[-1]["values"]["status"] == MinistryStatus.PENDING_APPROVAL.value
    assert stub.insert_approval_calls


@pytest.mark.asyncio
async def test_approve_ministry_as_incumbent_dispatches_decision_mail():
    ministry_id = uuid4()
    owner_position_id = uuid4()
    incumbent_user_id = uuid4()
    applicant_user_id = uuid4()
    ministry = _pending_ministry(ministry_id=ministry_id, owner_position_id=owner_position_id, submitted_by_id=applicant_user_id)
    stub = StubMinistryRepository(ministry_by_id={ministry_id: ministry})
    mail_port = StubMailSendPort()
    mail_service = make_mail_service(
        mail_port,
        stub,
        StubPositionRepository(incumbents={owner_position_id: incumbent_user_id}),
        StubMailUserRepository(
            users={applicant_user_id: UserSensitive(id=applicant_user_id, email="applicant@example.com", verified=True, is_active=True, is_admin=False)}
        ),
    )
    approval_service = make_approval_service(
        stub, position_stub=StubPositionRepository(incumbents={owner_position_id: incumbent_user_id}), mail_service=mail_service
    )
    approval_service._user_ctx = UserContext(user_id=incumbent_user_id, email="incumbent@example.com", is_admin=False, is_superuser=False)

    await approval_service.approve_ministry_as_incumbent(ministry_id, ApproveMinistryCommand())

    assert len(mail_port.calls) == 1
    assert mail_port.calls[0]["to_email"] == "applicant@example.com"
    assert "Approved" in mail_port.calls[0]["subject"]


@pytest.mark.asyncio
async def test_reject_ministry_as_incumbent_forbidden_for_non_incumbent():
    ministry_id = uuid4()
    owner_position_id = uuid4()
    ministry = _pending_ministry(ministry_id=ministry_id, owner_position_id=owner_position_id, submitted_by_id=uuid4())
    stub = StubMinistryRepository(ministry_by_id={ministry_id: ministry})
    approval_service = make_approval_service(stub, position_stub=StubPositionRepository(incumbents={owner_position_id: uuid4()}))
    approval_service._user_ctx = UserContext(user_id=uuid4(), email="other@example.com", is_admin=False, is_superuser=False)

    with pytest.raises(ForbiddenException) as exc_info:
        await approval_service.reject_ministry_as_incumbent(ministry_id, RejectMinistryCommand(rejection_reason="No"))
    assert exc_info.value.error_code == "ORG_MINISTRY_APPROVAL_FORBIDDEN"


@pytest.mark.asyncio
async def test_reject_ministry_as_incumbent_dispatches_decision_mail():
    ministry_id = uuid4()
    owner_position_id = uuid4()
    incumbent_user_id = uuid4()
    applicant_user_id = uuid4()
    ministry = _pending_ministry(ministry_id=ministry_id, owner_position_id=owner_position_id, submitted_by_id=applicant_user_id)
    stub = StubMinistryRepository(ministry_by_id={ministry_id: ministry})
    mail_port = StubMailSendPort()
    mail_service = make_mail_service(
        mail_port,
        stub,
        StubPositionRepository(incumbents={owner_position_id: incumbent_user_id}),
        StubMailUserRepository(
            users={applicant_user_id: UserSensitive(id=applicant_user_id, email="applicant@example.com", verified=True, is_active=True, is_admin=False)}
        ),
    )
    approval_service = make_approval_service(
        stub, position_stub=StubPositionRepository(incumbents={owner_position_id: incumbent_user_id}), mail_service=mail_service
    )
    approval_service._user_ctx = UserContext(user_id=incumbent_user_id, email="incumbent@example.com", is_admin=False, is_superuser=False)

    await approval_service.reject_ministry_as_incumbent(ministry_id, RejectMinistryCommand(rejection_reason="Incomplete roster"))

    assert len(mail_port.calls) == 1
    assert mail_port.calls[0]["to_email"] == "applicant@example.com"
    assert "Declined" in mail_port.calls[0]["subject"]
    assert "Incomplete roster" in mail_port.calls[0]["body_html"]


@pytest.mark.asyncio
async def test_admin_approve_ministry_dispatches_staff_decision_mails():
    ministry_id = uuid4()
    owner_position_id = uuid4()
    applicant_user_id = uuid4()
    incumbent_user_id = uuid4()
    staff_user_id = uuid4()
    ministry = _pending_ministry(ministry_id=ministry_id, owner_position_id=owner_position_id, submitted_by_id=applicant_user_id)
    stub = StubMinistryRepository(ministry_by_id={ministry_id: ministry})
    mail_port = StubMailSendPort()
    mail_service = make_mail_service(
        mail_port,
        stub,
        StubPositionRepository(incumbents={owner_position_id: incumbent_user_id}),
        StubMailUserRepository(
            users={
                applicant_user_id: UserSensitive(id=applicant_user_id, email="applicant@example.com", verified=True, is_active=True, is_admin=False),
                incumbent_user_id: UserSensitive(id=incumbent_user_id, email="incumbent@example.com", verified=True, is_active=True, is_admin=False),
                staff_user_id: UserSensitive(id=staff_user_id, email="staff@example.com", verified=True, is_active=True, is_admin=True),
            }
        ),
    )
    approval_service = make_approval_service(
        stub, position_stub=StubPositionRepository(incumbents={owner_position_id: incumbent_user_id}), mail_service=mail_service
    )
    approval_service._user_ctx = UserContext(user_id=staff_user_id, email="staff@example.com", is_admin=True, is_superuser=False)

    await approval_service.approve_ministry(ministry_id, ApproveMinistryCommand(decision_channel=MinistryDecisionChannel.STAFF))

    assert len(mail_port.calls) == 2
    assert {call["to_email"] for call in mail_port.calls} == {"applicant@example.com", "incumbent@example.com"}
    assert all("Approved" in call["subject"] or "Decision on Your Behalf" in call["subject"] for call in mail_port.calls)


@pytest.mark.asyncio
async def test_admin_reject_ministry_dispatches_staff_decision_mails():
    ministry_id = uuid4()
    owner_position_id = uuid4()
    applicant_user_id = uuid4()
    incumbent_user_id = uuid4()
    staff_user_id = uuid4()
    ministry = _pending_ministry(ministry_id=ministry_id, owner_position_id=owner_position_id, submitted_by_id=applicant_user_id)
    stub = StubMinistryRepository(ministry_by_id={ministry_id: ministry})
    mail_port = StubMailSendPort()
    mail_service = make_mail_service(
        mail_port,
        stub,
        StubPositionRepository(incumbents={owner_position_id: incumbent_user_id}),
        StubMailUserRepository(
            users={
                applicant_user_id: UserSensitive(id=applicant_user_id, email="applicant@example.com", verified=True, is_active=True, is_admin=False),
                incumbent_user_id: UserSensitive(id=incumbent_user_id, email="incumbent@example.com", verified=True, is_active=True, is_admin=False),
                staff_user_id: UserSensitive(id=staff_user_id, email="staff@example.com", verified=True, is_active=True, is_admin=True),
            }
        ),
    )
    approval_service = make_approval_service(
        stub, position_stub=StubPositionRepository(incumbents={owner_position_id: incumbent_user_id}), mail_service=mail_service
    )
    approval_service._user_ctx = UserContext(user_id=staff_user_id, email="staff@example.com", is_admin=True, is_superuser=False)

    await approval_service.reject_ministry(
        ministry_id, RejectMinistryCommand(rejection_reason="Incomplete roster", decision_channel=MinistryDecisionChannel.STAFF)
    )

    assert len(mail_port.calls) == 2
    assert {call["to_email"] for call in mail_port.calls} == {"applicant@example.com", "incumbent@example.com"}
    applicant_call = next(call for call in mail_port.calls if call["to_email"] == "applicant@example.com")
    assert "Declined" in applicant_call["subject"]
    assert "Incomplete roster" in applicant_call["body_html"]
    assert "staff@example.com" not in applicant_call["body_html"]
    assert "Church staff" in applicant_call["body_html"]
