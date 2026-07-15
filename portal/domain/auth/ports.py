"""
Auth domain ports.
"""
from datetime import datetime
from typing import Any, Optional, Protocol
from uuid import UUID

from portal.application.auth.results import UserDetail, UserSensitive
from portal.libs.consts.enums import ThirdPartyProvider


class UserRepositoryPort(Protocol):
    """Load and mutate user accounts."""

    async def get_sensitive_by_email(self, email: str) -> Optional[UserSensitive]:
        ...

    async def get_sensitive_by_email_without_profile(self, email: str) -> Optional[UserSensitive]:
        ...

    async def get_sensitive_by_id(self, user_id: UUID) -> Optional[UserSensitive]:
        ...

    async def get_detail_by_id(self, user_id: UUID) -> Optional[UserDetail]:
        ...

    async def user_profile_exists(self, user_id: UUID) -> bool:
        ...

    async def create_user_profile(
        self,
        user_id: UUID,
        first_name: str,
        last_name: str,
        preferred_name: Optional[str] = None,
    ) -> None:
        ...

    async def update_last_login_at(self, user_id: UUID, last_login_at) -> None:
        ...

    async def upsert_auth_user_third_party(
        self,
        user_id: UUID,
        provider: ThirdPartyProvider,
        provider_uid: str,
        provider_tenant_id: UUID,
        additional_data: dict[str, Any],
        token_expires_at: Optional[datetime] = None,
        access_token: Optional[str] = None,
        refresh_token: Optional[str] = None,
    ) -> None:
        ...

    async def get_user_id_by_third_party(
        self,
        provider: ThirdPartyProvider,
        provider_uid: str,
    ) -> Optional[UUID]:
        ...

    async def create_directory_user(
        self,
        user_id: UUID,
        email: str,
        *,
        verified: bool,
        is_active: bool,
        is_admin: bool,
        account_kind: str,
        first_name: str,
        last_name: str,
        preferred_name: Optional[str] = None,
    ) -> None:
        ...

    async def update_directory_user_profile(
        self,
        user_id: UUID,
        first_name: str,
        last_name: str,
        preferred_name: Optional[str] = None,
    ) -> None:
        ...

    async def update_user_active_flag(self, user_id: UUID, is_active: bool) -> None:
        ...
