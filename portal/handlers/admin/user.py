"""
Minimal AdminUserHandler for auth - get_user_detail_by_id only
"""
from typing import Optional
from uuid import UUID

from redis.asyncio import Redis

from portal.config import settings
from portal.libs.contexts.user_context import UserContext, get_user_context
from portal.libs.database import Session, RedisPool
from portal.models import PortalUser, PortalUserProfile
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
                PortalUser.id,
                PortalUser.phone_number,
                PortalUser.email,
                PortalUser.password_hash,
                PortalUser.verified,
                PortalUser.is_active,
                PortalUser.is_superuser,
                PortalUser.is_admin,
                PortalUser.password_changed_at,
                PortalUser.password_expires_at,
                PortalUser.last_login_at,
                PortalUserProfile.display_name,
                PortalUserProfile.gender,
                PortalUserProfile.is_ministry,
            )
            .join(PortalUserProfile, PortalUser.id == PortalUserProfile.user_id)
            .where(PortalUser.id == user_id)
            .where(PortalUser.is_deleted == False)
            .fetchrow(as_model=SUserSensitive)
        )
        if not user:
            return None
        return user
