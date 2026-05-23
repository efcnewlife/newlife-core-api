"""
Auth domain ports.
"""
from typing import Optional, Protocol
from uuid import UUID

from portal.application.auth.results import UserDetail, UserSensitive


class UserRepositoryPort(Protocol):
    """Load and mutate user accounts."""

    async def get_sensitive_by_email(self, email: str) -> Optional[UserSensitive]:
        ...

    async def get_sensitive_by_id(self, user_id: UUID) -> Optional[UserSensitive]:
        ...

    async def get_detail_by_id(self, user_id: UUID) -> Optional[UserDetail]:
        ...

    async def update_last_login_at(self, user_id: UUID, last_login_at) -> None:
        ...
