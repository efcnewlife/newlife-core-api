"""
Tests for UserReadService.
"""
from uuid import uuid4

import pytest

from portal.application.auth.results import UserDetail, UserSensitive
from portal.application.auth.user_read_service import UserReadService


class StubUserRepository:
    def __init__(self, detail=None, sensitive=None):
        self._detail = detail
        self._sensitive = sensitive
        self.detail_by_id_calls: list = []
        self.sensitive_by_id_calls: list = []
        self.sensitive_by_email_calls: list = []

    async def get_detail_by_id(self, user_id):
        self.detail_by_id_calls.append(user_id)
        return self._detail

    async def get_sensitive_by_id(self, user_id):
        self.sensitive_by_id_calls.append(user_id)
        return self._sensitive

    async def get_sensitive_by_email(self, email):
        self.sensitive_by_email_calls.append(email)
        return self._sensitive


@pytest.mark.asyncio
async def test_get_user_detail_by_id_returns_none_when_missing():
    user_id = uuid4()
    repo = StubUserRepository()
    service = UserReadService(repo)
    result = await service.get_user_detail_by_id(user_id)
    assert result is None
    assert repo.detail_by_id_calls == [user_id]


@pytest.mark.asyncio
async def test_get_user_detail_by_id_returns_user():
    user_id = uuid4()
    detail = UserDetail(
        id=user_id,
        email="user@example.com",
        verified=True,
        is_active=True,
        is_superuser=False,
        is_admin=False,
    )
    repo = StubUserRepository(detail=detail)
    service = UserReadService(repo)
    result = await service.get_user_detail_by_id(user_id)
    assert result is not None
    assert result.email == "user@example.com"


@pytest.mark.asyncio
async def test_get_user_sensitive_by_email():
    user_id = uuid4()
    sensitive = UserSensitive(
        id=user_id,
        email="admin@example.com",
        verified=True,
        is_active=True,
        is_superuser=False,
        is_admin=True,
        password_hash="hash",
    )
    repo = StubUserRepository(sensitive=sensitive)
    service = UserReadService(repo)
    result = await service.get_user_sensitive_by_email("admin@example.com")
    assert result is not None
    assert result.is_admin is True
    assert repo.sensitive_by_email_calls == ["admin@example.com"]
