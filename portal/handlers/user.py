"""
Minimal UserHandler for auth - get_user_detail_by_id only
"""
from typing import Optional
from uuid import UUID

import sqlalchemy as sa
from redis.asyncio import Redis

from portal.config import settings
from portal.libs.contexts.user_context import UserContext, get_user_context
from portal.libs.database import Session, RedisPool
from portal.models import AuthUser, AuthUserProfile
from portal.schemas.user import SUserDetail


class UserHandler:
    """UserHandler - minimal implementation for auth"""

    def __init__(self, session: Session, redis_client: RedisPool):
        self._session = session
        self._redis: Redis = redis_client.create(db=settings.REDIS_DB)
        self._user_ctx: Optional[UserContext] = get_user_context()

    async def get_user_detail_by_id(self, user_id: UUID) -> Optional[SUserDetail]:
        """
        Get user detail by id
        :param user_id:
        :return:
        """
        display_name_expr = sa.func.trim(
            sa.func.concat(
                sa.func.coalesce(AuthUserProfile.first_name, ""),
                " ",
                sa.func.coalesce(AuthUserProfile.last_name, ""),
            )
        ).label("display_name")
        user: SUserDetail = await (
            self._session.select(
                AuthUser.id,
                AuthUser.phone_number,
                AuthUser.email,
                AuthUser.verified,
                AuthUser.is_active,
                AuthUser.is_superuser,
                AuthUser.is_admin,
                AuthUser.last_login_at,
                AuthUserProfile.first_name,
                AuthUserProfile.last_name,
                AuthUserProfile.gender,
            )
            .join(AuthUserProfile, AuthUser.id == AuthUserProfile.user_id)
            .where(AuthUser.id == user_id)
            .where(AuthUser.is_deleted == False)
            .fetchrow(as_model=SUserDetail)
        )
        if not user:
            return None
        return user
