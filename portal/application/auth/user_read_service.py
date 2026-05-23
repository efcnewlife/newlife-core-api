"""
User read service for auth middleware and token validation.
"""
from typing import Optional
from uuid import UUID

from portal.application.auth.results import UserDetail, UserSensitive
from portal.domain.auth.ports import UserRepositoryPort
from portal.libs.tracing.distributed_trace import distributed_trace


class UserReadService:
    """Read-only user lookups for authentication."""

    def __init__(self, user_repository: UserRepositoryPort):
        self._repository = user_repository

    @distributed_trace()
    async def get_user_detail_by_id(self, user_id: UUID) -> Optional[UserDetail]:
        return await self._repository.get_detail_by_id(user_id)

    @distributed_trace()
    async def get_user_sensitive_by_id(self, user_id: UUID) -> Optional[UserSensitive]:
        return await self._repository.get_sensitive_by_id(user_id)

    @distributed_trace()
    async def get_user_sensitive_by_email(self, email: str) -> Optional[UserSensitive]:
        return await self._repository.get_sensitive_by_email(email)
