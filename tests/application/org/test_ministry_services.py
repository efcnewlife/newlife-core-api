"""
Org application unit tests.
"""
from datetime import time
from uuid import uuid4

import pytest
from pydantic import ValidationError

from portal.application.org.commands import (
    CreateMinistryCommand,
    MinistryMemberEntryCommand,
    MinistryScheduleCommand,
    OrgTranslationCommand,
    ReplaceMinistryMembersCommand,
    SubmitMinistryCommand,
)
from portal.application.org.ministry_approval_service import MinistryApprovalService
from portal.application.org.ministry_schedule import validate_ministry_schedules
from portal.application.org.ministry_service import MinistryService
from portal.application.org.results import MinistryDetailResult, MinistryMemberResult, TargetAudienceResult
from portal.application.org.target_audience_validation import validate_target_audience_ids
from portal.domain.facility.days_of_week_mask import days_to_mask, mask_to_days
from portal.domain.org.catalog_codes import TARGET_AUDIENCE_ADULTS, TARGET_AUDIENCE_ALL_AGES
from portal.domain.org.constants import MinistryMemberRole, MinistryStatus
from portal.exceptions.responses import BadRequestException
from tests.fixtures.org.stubs import (
    StubMinistryRepository,
    StubMinistryTypeRepository,
    StubTargetAudienceRepository,
)


def make_service(
    ministry_stub: StubMinistryRepository | None = None,
    type_stub: StubMinistryTypeRepository | None = None,
    audience_stub: StubTargetAudienceRepository | None = None,
) -> MinistryService:
    return MinistryService(
        ministry_stub or StubMinistryRepository(),
        type_stub or StubMinistryTypeRepository(),
        audience_stub or StubTargetAudienceRepository(),
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
            ministry_id: MinistryDetailResult(
                id=ministry_id,
                name="Youth",
                status=MinistryStatus.DRAFT.value,
                has_priority_booking=False,
                is_active=True,
            )
        }
    )
    approval_service = MinistryApprovalService(stub, make_service(stub))
    with pytest.raises(BadRequestException, match="owner_position_id"):
        await approval_service.submit_ministry(ministry_id, SubmitMinistryCommand())


@pytest.mark.asyncio
async def test_validate_members_for_submit_requires_primary_and_secondary():
    ministry_id = uuid4()
    stub = StubMinistryRepository(
        ministry_by_id={
            ministry_id: MinistryDetailResult(
                id=ministry_id,
                name="Youth",
                status=MinistryStatus.DRAFT.value,
                has_priority_booking=False,
                is_active=True,
            )
        },
        members_by_ministry={
            ministry_id: [
                MinistryMemberResult(
                    user_id=uuid4(),
                    member_role=MinistryMemberRole.PRIMARY.value,
                )
            ]
        },
    )
    service = make_service(stub)
    with pytest.raises(BadRequestException, match="secondary"):
        await service.validate_members_for_submit(ministry_id)


@pytest.mark.asyncio
async def test_replace_members_success():
    ministry_id = uuid4()
    primary_id = uuid4()
    secondary_id = uuid4()
    stub = StubMinistryRepository(
        ministry_by_id={
            ministry_id: MinistryDetailResult(
                id=ministry_id,
                name="Youth",
                status=MinistryStatus.DRAFT.value,
                has_priority_booking=False,
                is_active=True,
            )
        }
    )
    service = make_service(stub)
    await service.replace_members(
        ministry_id,
        ReplaceMinistryMembersCommand(
            members=[
                MinistryMemberEntryCommand(
                    user_id=primary_id,
                    member_role=MinistryMemberRole.PRIMARY,
                    contact_email="primary@example.com",
                ),
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
        CreateMinistryCommand(
            translations=[OrgTranslationCommand(locale_id=locale_id, name="Youth Ministry", schedule_note="Summer off")],
        )
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
    audience_stub = StubTargetAudienceRepository(
        {adults_id: TargetAudienceResult(id=adults_id, code=TARGET_AUDIENCE_ADULTS)}
    )
    service = make_service(stub, audience_stub=audience_stub)
    locale_id = uuid4()
    ministry_type_id = uuid4()
    type_stub = StubMinistryTypeRepository(default_type_id=ministry_type_id)
    service = make_service(stub, type_stub=type_stub, audience_stub=audience_stub)
    await service.create_ministry(
        CreateMinistryCommand(
            ministry_type_id=ministry_type_id,
            target_audience_ids=[adults_id],
            schedules=[
                MinistryScheduleCommand(
                    days_of_week=[0, 6],
                    start_time=time(13, 30),
                    end_time=time(16, 30),
                )
            ],
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
    with pytest.raises(BadRequestException):
        validate_target_audience_ids(
            [all_ages_id, adults_id],
            [
                TargetAudienceResult(id=all_ages_id, code=TARGET_AUDIENCE_ALL_AGES),
                TargetAudienceResult(id=adults_id, code=TARGET_AUDIENCE_ADULTS),
            ],
        )
