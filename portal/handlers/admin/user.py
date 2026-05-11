"""
AdminUserHandler
"""
import uuid
from typing import Optional
from uuid import UUID

import sqlalchemy as sa
from asyncpg import UniqueViolationError
from redis.asyncio import Redis

from portal.config import settings
from portal.exceptions.responses import (
    UnauthorizedException,
    BadRequestException,
    ConflictErrorException,
)
from portal.libs.contexts.user_context import UserContext, get_user_context
from portal.libs.database import Session, RedisPool
from portal.models import AuthUser, AuthUserProfile, AuthUserRole, SystemLocale
from portal.providers.password_provider import PasswordProvider
from portal.schemas.mixins import UUIDBaseModel
from portal.schemas.user import SUserSensitive
from portal.serializers.admin.v1.user import (
    AdminUserQuery,
    AdminUserPages,
    AdminUserTableItem,
    AdminUserBase,
    AdminUserList,
    AdminUserItem,
    AdminUserCreate,
    AdminUserUpdate,
    AdminUserBulkAction,
    AdminChangePassword,
    AdminBindRole,
    AdminUserRoles,
)
from portal.serializers.mixins import DeleteBaseModel


class AdminUserHandler:
    """AdminUserHandler"""

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
                AuthUserProfile.preferred_locale_id,
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
                AuthUserProfile.preferred_locale_id,
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

    async def get_user_pages(self, model: AdminUserQuery) -> AdminUserPages:
        """
        Get user pages.
        """
        items, count = await (
            self._session.select(
                AuthUser.id,
                AuthUser.phone_number,
                AuthUser.email,
                AuthUser.verified,
                AuthUser.is_active,
                AuthUser.is_superuser,
                AuthUser.is_admin,
                AuthUser.created_at,
                AuthUser.updated_at,
                AuthUser.last_login_at,
                AuthUserProfile.first_name,
                AuthUserProfile.last_name,
                AuthUserProfile.preferred_name,
                AuthUserProfile.preferred_locale_id,
                AuthUserProfile.gender,
            )
            .join(AuthUserProfile, AuthUser.id == AuthUserProfile.user_id)
            .where(AuthUser.is_deleted == model.deleted)
            .where(
                model.keyword,
                lambda: sa.or_(
                    AuthUser.phone_number.ilike(f"%{model.keyword}%"),
                    AuthUser.email.ilike(f"%{model.keyword}%"),
                    AuthUserProfile.first_name.ilike(f"%{model.keyword}%"),
                    AuthUserProfile.last_name.ilike(f"%{model.keyword}%"),
                    AuthUserProfile.preferred_name.ilike(f"%{model.keyword}%"),
                ),
            )
            .where(model.verified is not None, lambda: AuthUser.verified == model.verified)
            .where(model.is_active is not None, lambda: AuthUser.is_active == model.is_active)
            .where(model.is_admin is not None, lambda: AuthUser.is_admin == model.is_admin)
            .where(model.is_superuser is not None, lambda: AuthUser.is_superuser == model.is_superuser)
            .where(model.gender is not None, lambda: AuthUserProfile.gender == model.gender)
            .order_by_with(
                tables=[AuthUser, AuthUserProfile],
                order_by=model.order_by,
                descending=model.descending,
            )
            .limit(model.page_size)
            .offset(model.page * model.page_size)
            .fetchpages(
                no_order_by=False,
                as_model=AdminUserTableItem,
            )
        )
        return AdminUserPages(
            page=model.page,
            page_size=model.page_size,
            total=count,
            items=items,
        )

    async def get_user_list(self, keyword: Optional[str] = None) -> AdminUserList:
        """
        Get user list.
        """
        users: list[AdminUserBase] = await (
            self._session.select(
                AuthUser.id,
                AuthUser.phone_number,
                AuthUser.email,
                AuthUserProfile.preferred_name.label("display_name"),
            )
            .join(AuthUserProfile, AuthUser.id == AuthUserProfile.user_id)
            .where(
                keyword,
                lambda: sa.or_(
                    AuthUser.phone_number.ilike(f"%{keyword}%"),
                    AuthUser.email.ilike(f"%{keyword}%"),
                    AuthUserProfile.preferred_name.ilike(f"%{keyword}%"),
                    AuthUserProfile.first_name.ilike(f"%{keyword}%"),
                    AuthUserProfile.last_name.ilike(f"%{keyword}%"),
                ),
            )
            .where(AuthUser.is_deleted == False)
            .where(AuthUser.is_active == True)
            .order_by(AuthUser.created_at.asc())
            .limit(100)
            .fetch(as_model=AdminUserBase)
        )
        return AdminUserList(items=users)

    async def get_user_list_with_device_token(self, keyword: Optional[str] = None) -> AdminUserList:
        """
        Get user list with device token.
        """
        return await self.get_user_list(keyword=keyword)

    async def get_user_by_id(self, user_id: UUID) -> Optional[AdminUserItem]:
        """
        Get user by id.
        """
        user = await (
            self._session.select(
                AuthUser.id,
                AuthUser.phone_number,
                AuthUser.email,
                AuthUser.verified,
                AuthUser.is_active,
                AuthUser.is_superuser,
                AuthUser.is_admin,
                AuthUser.created_at,
                AuthUser.updated_at,
                AuthUser.last_login_at,
                AuthUserProfile.first_name,
                AuthUserProfile.last_name,
                AuthUserProfile.preferred_name,
                AuthUserProfile.preferred_locale_id,
                AuthUserProfile.gender,
            )
            .join(AuthUserProfile, AuthUser.id == AuthUserProfile.user_id)
            .where(AuthUser.id == user_id)
            .where(AuthUser.is_deleted == False)
            .fetchrow(as_model=AdminUserItem)
        )
        return user

    async def get_current_user(self) -> Optional[AdminUserItem]:
        """
        Get current user detail by auth context.
        """
        if not self._user_ctx or not self._user_ctx.user_id:
            raise UnauthorizedException(detail="Unauthorized")
        return await self.get_user_by_id(self._user_ctx.user_id)

    async def create_user(self, model: AdminUserCreate) -> UUIDBaseModel:
        """
        Create user.
        """
        if model.password != model.password_confirm:
            raise BadRequestException(detail="Passwords do not match")
        if not self._password_provider.validate_password(model.password):
            raise BadRequestException(detail="Password is not valid")
        user_id = uuid.uuid4()
        password_hash = self._password_provider.hash_password(model.password)
        try:
            await (
                self._session.insert(AuthUser)
                .values(
                    id=user_id,
                    phone_number=model.phone_number,
                    email=model.email,
                    password_hash=password_hash,
                    verified=model.verified,
                    is_active=model.is_active,
                    is_superuser=model.is_superuser,
                    is_admin=model.is_admin,
                    remark=model.remark,
                )
                .execute()
            )
            await (
                self._session.insert(AuthUserProfile)
                .values(
                    user_id=user_id,
                    first_name=model.display_name or "",
                    last_name="",
                    preferred_name=model.display_name,
                    gender=model.gender.value if model.gender is not None else None,
                )
                .execute()
            )
        except UniqueViolationError as error:
            raise ConflictErrorException(detail="User already exists", debug_detail=str(error))
        return UUIDBaseModel(id=user_id)

    async def update_current_user(self, model: AdminUserUpdate) -> None:
        """
        Update current user.
        """
        if not self._user_ctx or not self._user_ctx.user_id:
            raise UnauthorizedException(detail="Unauthorized")
        await self.update_user(user_id=self._user_ctx.user_id, model=model)

    async def update_user(self, user_id: UUID, model: AdminUserUpdate) -> None:
        """
        Update user.
        """
        try:
            await (
                self._session.update(AuthUser)
                .values(
                    phone_number=model.phone_number,
                    email=model.email,
                    verified=model.verified,
                    is_active=model.is_active,
                    is_superuser=model.is_superuser,
                    is_admin=model.is_admin,
                    remark=model.remark,
                    updated_at=sa.func.now(),
                )
                .where(AuthUser.id == user_id)
                .execute()
            )
            await (
                self._session.update(AuthUserProfile)
                .values(
                    preferred_name=model.display_name,
                    first_name=model.display_name or "",
                    gender=model.gender.value if model.gender is not None else None,
                    updated_at=sa.func.now(),
                )
                .where(AuthUserProfile.user_id == user_id)
                .execute()
            )
        except UniqueViolationError as error:
            raise ConflictErrorException(detail="User already exists", debug_detail=str(error))

    async def delete_user(self, user_id: UUID, model: DeleteBaseModel) -> None:
        """
        Soft delete user.
        """
        await (
            self._session.update(AuthUser)
            .values(is_deleted=True, delete_reason=model.reason)
            .where(AuthUser.id == user_id)
            .execute()
        )

    async def restore_user(self, model: AdminUserBulkAction) -> None:
        """
        Restore users.
        """
        if not model.ids:
            raise BadRequestException(detail="No user ids provided")
        await (
            self._session.update(AuthUser)
            .values(is_deleted=False, delete_reason=None)
            .where(AuthUser.id.in_(model.ids))
            .execute()
        )

    async def get_user_roles(self, user_id: UUID) -> AdminUserRoles:
        """
        Get user role ids.
        """
        roles: list[UUID] = await (
            self._session.select(AuthUserRole.role_id)
            .where(AuthUserRole.user_id == user_id)
            .fetchvals()
        )
        return AdminUserRoles(role_ids=roles)

    async def bind_roles(self, user_id: UUID, model: AdminBindRole) -> None:
        """
        Bind roles to user.
        """
        original_roles = await (
            self._session.select(AuthUserRole.role_id)
            .where(AuthUserRole.user_id == user_id)
            .fetchvals()
        )
        new_role_ids = set(model.role_ids or [])
        old_role_ids = set(original_roles)
        insert_role_ids = list(new_role_ids - old_role_ids)
        delete_role_ids = list(old_role_ids - new_role_ids)

        if insert_role_ids:
            await (
                self._session.insert(AuthUserRole)
                .values(
                    [{"user_id": user_id, "role_id": role_id} for role_id in insert_role_ids]
                )
                .on_conflict_do_nothing(index_elements=["user_id", "role_id"])
                .execute()
            )
        if delete_role_ids:
            await (
                self._session.delete(AuthUserRole)
                .where(AuthUserRole.user_id == user_id)
                .where(AuthUserRole.role_id.in_(delete_role_ids))
                .execute()
            )

    async def change_password(self, user_id: UUID, model: AdminChangePassword) -> None:
        """
        Change user password.
        """
        user = await self.get_user_detail_by_id(user_id=user_id)
        if not user:
            raise BadRequestException(detail="User not found")
        if not self._user_ctx or user.id != self._user_ctx.user_id:
            raise UnauthorizedException(detail="Unauthorized")
        if not self._password_provider.verify_password(model.old_password, user.password_hash):
            raise BadRequestException(detail="Old password is not valid")
        if model.new_password != model.new_password_confirm:
            raise BadRequestException(detail="New passwords do not match")
        if not self._password_provider.validate_password(model.new_password):
            raise BadRequestException(detail="New password is not valid")
        password_hash = self._password_provider.hash_password(model.new_password)
        await (
            self._session.update(AuthUser)
            .values(
                password_hash=password_hash,
                updated_at=sa.func.now(),
                password_changed_at=sa.func.now(),
            )
            .where(AuthUser.id == user_id)
            .execute()
        )

    async def update_current_user_preferred_locale(self, preferred_locale_id: UUID) -> None:
        """
        Update preferred locale for current user.
        """
        if not self._user_ctx or not self._user_ctx.user_id:
            raise UnauthorizedException(detail="Unauthorized")
        locale_exists = await (
            self._session.select(SystemLocale.id)
            .where(SystemLocale.id == preferred_locale_id)
            .where(SystemLocale.is_deleted == False)
            .fetchval()
        )
        if not locale_exists:
            raise BadRequestException(detail="Preferred language is invalid")
        await (
            self._session.update(AuthUserProfile)
            .where(AuthUserProfile.user_id == self._user_ctx.user_id)
            .values(preferred_locale_id=preferred_locale_id)
            .execute()
        )
