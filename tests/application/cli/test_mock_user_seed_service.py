"""
Tests for mock testing-account seed service.
"""

from uuid import uuid4

import pytest

from portal.application.cli.mock_user_seed_service import MockUserSeedService, email_has_testing_suffix
from portal.domain.member.constants import AccountKind


class StubSession:
    def __init__(self, *, existing_email: str | None = None):
        self.existing_email = existing_email
        self.inserted_auth_users: list[dict] = []
        self.inserted_profiles: list[dict] = []
        self.committed = False
        self._created_user_id = uuid4()

    def select(self, *args, **kwargs):
        return self

    def where(self, *args, **kwargs):
        return self

    async def fetchval(self):
        if self.existing_email:
            return uuid4()
        return None

    async def fetchrow(self):
        return {"id": self._created_user_id}

    def insert(self, model):
        self._insert_model = model
        return self

    def values(self, **kwargs):
        if self._insert_model.__name__ == "AuthUser":
            self.inserted_auth_users.append(kwargs)
        else:
            self.inserted_profiles.append(kwargs)
        return self

    async def execute(self):
        return None

    async def commit(self):
        self.committed = True


@pytest.mark.parametrize(
    ("email", "suffix", "expected"),
    [
        ("qa.owner@test.local", "@test.local", True),
        ("qa.owner@example.com", "@test.local", False),
        ("user@qa.test", "@qa.test", True),
        ("user@test.local", "", False),
    ],
)
def test_email_has_testing_suffix(email: str, suffix: str, expected: bool):
    assert email_has_testing_suffix(email, suffix=suffix) is expected


@pytest.mark.asyncio
async def test_create_mock_user_inserts_member_account():
    session = StubSession()
    service = MockUserSeedService(session)

    await service.run(email="qa.owner@test.local", first_name="QA", last_name="Owner")

    assert session.committed is True
    assert len(session.inserted_auth_users) == 1
    user_row = session.inserted_auth_users[0]
    assert user_row["email"] == "qa.owner@test.local"
    assert user_row["verified"] is True
    assert user_row["is_active"] is True
    assert user_row["is_admin"] is False
    assert user_row["is_superuser"] is False
    assert user_row["account_kind"] == AccountKind.MEMBER.value
    assert "password_hash" not in user_row

    assert len(session.inserted_profiles) == 1
    profile_row = session.inserted_profiles[0]
    assert profile_row["first_name"] == "QA"
    assert profile_row["last_name"] == "Owner"


@pytest.mark.asyncio
async def test_create_mock_user_rejects_non_testing_suffix():
    session = StubSession()
    service = MockUserSeedService(session)

    with pytest.raises(ValueError, match="testing suffix"):
        await service.run(email="qa.owner@example.com", first_name="QA", last_name="Owner")

    assert session.committed is False
    assert session.inserted_auth_users == []


@pytest.mark.asyncio
async def test_create_mock_user_returns_existing_without_insert():
    session = StubSession(existing_email="existing@test.local")
    service = MockUserSeedService(session)

    result = await service.run(email="existing@test.local", first_name="Existing", last_name="User")

    assert result is not None
    assert session.committed is False
    assert session.inserted_auth_users == []
