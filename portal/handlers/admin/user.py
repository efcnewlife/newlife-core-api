"""
Minimal AdminUserHandler for auth - get_user_detail_by_id only
"""
from typing import Optional, Tuple
from uuid import UUID

import sqlalchemy as sa
from redis.asyncio import Redis

from portal.config import settings
from portal.libs.contexts.user_context import UserContext, get_user_context
from portal.libs.database import Session, RedisPool
from portal.models import (
    AuthUser,
    AuthUserProfile,
    AuthUserRole,
    AuthRole,
    AuthRolePermission,
    AuthPermission,
)
from portal.providers.password_provider import PasswordProvider
from portal.schemas.user import SUserSensitive


class AdminUserHandler:
    """AdminUserHandler - minimal implementation for auth"""

    def __init__(
        self,
        session: Session,
        redis_client: RedisPool,
        password_provider: PasswordProvider,
    ):
        self._session = session
        self._redis: Redis = redis_client.create(db=settings.REDIS_DB)
        self._password_provider = password_provider
        self._user_ctx: Optional[UserContext] = get_user_context()

    async def get_user_detail_by_id(self, user_id: UUID) -> Optional[SUserSensitive]:
        """
        Get user detail by id
        :param user_id:
        :return:
        """
        user: SUserSensitive = await (
            self._session.select(
                AuthUser.id,
                AuthUser.phone_number,
                AuthUser.email,
                AuthUser.password_hash,
                AuthUser.verified,
                AuthUser.is_active,
                AuthUser.is_superuser,
                AuthUser.is_admin,
                AuthUser.password_changed_at,
                AuthUser.password_expires_at,
                AuthUser.last_login_at,
                AuthUserProfile.first_name,
                AuthUserProfile.last_name,
                AuthUserProfile.preferred_name,
                AuthUserProfile.gender,
            )
            .join(AuthUserProfile, AuthUser.id == AuthUserProfile.user_id)
            .where(AuthUser.id == user_id)
            .where(AuthUser.is_deleted == False)
            .fetchrow(as_model=SUserSensitive)
        )
        if not user:
            return None
        return user

    async def get_user_detail_by_email(self, email: str) -> Optional[SUserSensitive]:
        """
        Get admin-eligible user by email (case-insensitive).
        """
        if not email:
            return None
        normalized = email.strip().lower()
        user: SUserSensitive = await (
            self._session.select(
                AuthUser.id,
                AuthUser.phone_number,
                AuthUser.email,
                AuthUser.password_hash,
                AuthUser.verified,
                AuthUser.is_active,
                AuthUser.is_superuser,
                AuthUser.is_admin,
                AuthUser.password_changed_at,
                AuthUser.password_expires_at,
                AuthUser.last_login_at,
                AuthUserProfile.first_name,
                AuthUserProfile.last_name,
                AuthUserProfile.gender
            )
            .join(AuthUserProfile, AuthUser.id == AuthUserProfile.user_id)
            .where(sa.func.lower(AuthUser.email) == normalized)
            .where(AuthUser.is_deleted == False)
            .fetchrow(as_model=SUserSensitive)
        )
        if not user:
            return None
        return user

    async def list_role_codes_and_permission_codes(self, user_id: UUID) -> Tuple[list[str], list[str]]:
        """
        Return distinct role codes and permission codes for RBAC-backed JWT scope.
        """
        role_raw = await (
            self._session.select(AuthRole.code)
            .join(AuthUserRole, AuthUserRole.role_id == AuthRole.id)
            .where(AuthUserRole.user_id == user_id)
            .where(AuthRole.is_active == True)
            .fetchvals()
        )
        role_codes = list(dict.fromkeys(c for c in (role_raw or []) if c))

        perm_raw = await (
            self._session.select(AuthPermission.code)
            .join(AuthRolePermission, AuthRolePermission.permission_id == AuthPermission.id)
            .join(AuthUserRole, AuthUserRole.role_id == AuthRolePermission.role_id)
            .where(AuthUserRole.user_id == user_id)
            .where(AuthPermission.is_active == True)
            .fetchvals()
        )
        permission_codes = sorted(
            {c for c in (perm_raw or []) if c and ":" in str(c)}
        )

        return role_codes, permission_codes
