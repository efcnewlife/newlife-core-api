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
