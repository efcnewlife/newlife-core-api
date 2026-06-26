"""
MemberService unit tests.
"""
from uuid import uuid4

import pytest

from portal.application.facility.commands import ReplaceMinistryMemberCommand
from portal.application.facility.member_service import MemberService
from portal.exceptions.responses import NotFoundException
from tests.fixtures.facility.factories import make_member_detail, new_uuid
from tests.fixtures.facility.stubs import StubMemberRepository, StubMinistryRepository


@pytest.mark.asyncio
async def test_get_member_by_id_not_found():
    service = MemberService(StubMemberRepository(), StubMinistryRepository())
    with pytest.raises(NotFoundException, match="Member not found"):
        await service.get_member_by_id(uuid4())


@pytest.mark.asyncio
async def test_replace_user_ministries_not_found():
    service = MemberService(StubMemberRepository(), StubMinistryRepository())
    with pytest.raises(NotFoundException):
        await service.replace_user_ministries(uuid4(), ReplaceMinistryMemberCommand(ministry_ids=[]))


@pytest.mark.asyncio
async def test_replace_user_ministries_calls_repository(monkeypatch):
    user_id = new_uuid()
    ministry_id = new_uuid()
    member_stub = StubMemberRepository(member_by_id={user_id: make_member_detail(user_id)})
    ministry_stub = StubMinistryRepository()

    class UserCtx:
        user_id = uuid4()

    monkeypatch.setattr(
        "portal.application.facility.member_service.get_user_context",
        lambda: UserCtx(),
    )
    service = MemberService(member_stub, ministry_stub)
    await service.replace_user_ministries(user_id, ReplaceMinistryMemberCommand(ministry_ids=[ministry_id]))
    assert ministry_stub.replace_user_ministries_calls[0]["ministry_ids"] == [ministry_id]
