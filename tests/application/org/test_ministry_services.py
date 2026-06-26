"""
Org application unit tests.
"""
from uuid import uuid4

import pytest
from pydantic import ValidationError

from portal.application.org.commands import (
    CreateMinistryCommand,
    MinistryMemberEntryCommand,
    OrgTranslationCommand,
    ReplaceMinistryMembersCommand,
    SubmitMinistryCommand,
)
from portal.application.org.ministry_approval_service import MinistryApprovalService
from portal.application.org.ministry_service import MinistryService
from portal.application.org.results import MinistryDetailResult, MinistryMemberResult
from portal.domain.org.constants import MinistryMemberRole, MinistryStatus
from portal.exceptions.responses import BadRequestException, NotFoundException
from tests.fixtures.org.stubs import StubMinistryRepository


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
    approval_service = MinistryApprovalService(stub, MinistryService(stub))
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
    service = MinistryService(stub)
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
    service = MinistryService(stub)
    await service.replace_members(
        ministry_id,
        ReplaceMinistryMembersCommand(
            members=[
                MinistryMemberEntryCommand(user_id=primary_id, member_role=MinistryMemberRole.PRIMARY),
                MinistryMemberEntryCommand(user_id=secondary_id, member_role=MinistryMemberRole.SECONDARY),
            ]
        ),
    )
    assert len(stub.replace_members_calls) == 1


@pytest.mark.asyncio
async def test_create_ministry_with_translation():
    stub = StubMinistryRepository()
    service = MinistryService(stub)
    locale_id = uuid4()
    result = await service.create_ministry(
        CreateMinistryCommand(
            translations=[OrgTranslationCommand(locale_id=locale_id, name="Youth Ministry")],
        )
    )
    assert result.id is not None
    assert len(stub.insert_calls) == 1
    assert stub.upsert_translation_calls
