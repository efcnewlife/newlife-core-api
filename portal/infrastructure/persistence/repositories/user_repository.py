"""
User repository implementation (merged UserHandler + AdminUserHandler SQL).
"""
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID, uuid4

import sqlalchemy as sa
from asyncpg import UniqueViolationError

from portal.application.auth.results import UserDetail, UserSensitive
from portal.application.rbac.commands import (
    AdminUserPagesQueryCommand,
    CreateAdminUserCommand,
    DeleteCommand,
    UpdateAdminUserCommand,
)
from portal.application.rbac.results import (
    AdminUserDetailResult,
    AdminUserListItem,
    AdminUserTableRow,
    CreateIdResult,
)
from portal.exceptions.responses import ConflictErrorException
from portal.libs.consts.enums import Gender, ThirdPartyProvider
from portal.libs.database import Session
from portal.models import (
    AuthUser,
    AuthUserProfile,
    AuthUserRole,
    AuthUserThirdParty,
    SystemLocale,
)


class UserRepository:
    """SQLAlchemy-backed user persistence."""

    def __init__(self, session: Session):
        self._session = session

    async def get_detail_by_id(self, user_id: UUID) -> Optional[UserDetail]:
        user: UserDetail = await (
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
            .fetchrow(as_model=UserDetail)
        )
        return user

    async def get_sensitive_by_id(self, user_id: UUID) -> Optional[UserSensitive]:
        user: UserSensitive = await (
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
            .fetchrow(as_model=UserSensitive)
        )
        return user

    async def get_sensitive_by_email(self, email: str) -> Optional[UserSensitive]:
        if not email:
            return None
        normalized = email.strip().lower()
        user: UserSensitive = await (
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
                AuthUserProfile.gender,
            )
            .join(AuthUserProfile, AuthUser.id == AuthUserProfile.user_id)
            .where(sa.func.lower(AuthUser.email) == normalized)
            .where(AuthUser.is_deleted == False)
            .fetchrow(as_model=UserSensitive)
        )
        return user

    async def get_sensitive_by_email_without_profile(self, email: str) -> Optional[UserSensitive]:
        """Load auth account by email without requiring an AuthUserProfile row."""
        if not email:
            return None
        normalized = email.strip().lower()
        user: UserSensitive = await (
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
            )
            .where(sa.func.lower(AuthUser.email) == normalized)
            .where(AuthUser.is_deleted == False)
            .fetchrow(as_model=UserSensitive)
        )
        return user

    async def user_profile_exists(self, user_id: UUID) -> bool:
        profile_id = await (
            self._session.select(AuthUserProfile.id)
            .where(AuthUserProfile.user_id == user_id)
            .fetchval()
        )
        return bool(profile_id)

    async def get_user_id_by_third_party(
        self,
        provider: ThirdPartyProvider,
        provider_uid: str,
    ) -> Optional[UUID]:
        user_id = await (
            self._session.select(AuthUserThirdParty.user_id)
            .where(AuthUserThirdParty.provider == provider.value)
            .where(AuthUserThirdParty.provider_uid == provider_uid)
            .where(AuthUserThirdParty.is_deleted == False)
            .fetchval()
        )
        return user_id

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
        await (
            self._session.insert(AuthUser)
            .values(
                id=user_id,
                email=email.strip().lower(),
                verified=verified,
                is_active=is_active,
                is_admin=is_admin,
                is_superuser=False,
                account_kind=account_kind,
                created_by="microsoft_graph_sync",
                updated_by="microsoft_graph_sync",
            )
            .execute()
        )
        await (
            self._session.insert(AuthUserProfile)
            .values(
                user_id=user_id,
                first_name=first_name[:64],
                last_name=last_name[:64],
                preferred_name=(preferred_name[:64] if preferred_name else None),
                gender=Gender.UNKNOWN.value,
                created_by="microsoft_graph_sync",
                updated_by="microsoft_graph_sync",
            )
            .execute()
        )

    async def update_directory_user_profile(
        self,
        user_id: UUID,
        first_name: str,
        last_name: str,
        preferred_name: Optional[str] = None,
    ) -> None:
        await (
            self._session.update(AuthUserProfile)
            .where(AuthUserProfile.user_id == user_id)
            .values(
                first_name=first_name[:64],
                last_name=last_name[:64],
                preferred_name=(preferred_name[:64] if preferred_name else None),
                updated_by="microsoft_graph_sync",
            )
            .execute()
        )

    async def update_user_active_flag(self, user_id: UUID, is_active: bool) -> None:
        await (
            self._session.update(AuthUser)
            .where(AuthUser.id == user_id)
            .values(is_active=is_active, updated_by="microsoft_graph_sync")
            .execute()
        )

    async def create_user_profile(
        self,
        user_id: UUID,
        first_name: str,
        last_name: str,
        preferred_name: Optional[str] = None,
    ) -> None:
        await (
            self._session.insert(AuthUserProfile)
            .values(
                user_id=user_id,
                first_name=first_name,
                last_name=last_name,
                preferred_name=preferred_name,
                gender=Gender.UNKNOWN.value,
                created_by="microsoft_oauth",
                updated_by="microsoft_oauth",
            )
            .execute()
        )

    async def get_user_pages(
        self,
        model: AdminUserPagesQueryCommand,
    ) -> tuple[list[AdminUserTableRow], int]:
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
                as_model=AdminUserTableRow,
            )
        )
        return items, count

    async def get_user_list(self, keyword: Optional[str] = None) -> list[AdminUserListItem]:
        users: list[AdminUserListItem] = await (
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
            .fetch(as_model=AdminUserListItem)
        )
        return users or []

    async def get_user_by_id(self, user_id: UUID) -> Optional[AdminUserDetailResult]:
        return await (
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
            .fetchrow(as_model=AdminUserDetailResult)
        )

    async def create_user(
        self,
        user_id: UUID,
        model: CreateAdminUserCommand,
        password_hash: str,
    ) -> CreateIdResult:
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
        return CreateIdResult(id=user_id)

    async def update_user(self, user_id: UUID, model: UpdateAdminUserCommand) -> None:
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

    async def delete_user(self, user_id: UUID, model: DeleteCommand) -> None:
        await (
            self._session.update(AuthUser)
            .values(is_deleted=True, delete_reason=model.reason)
            .where(AuthUser.id == user_id)
            .execute()
        )

    async def restore_users(self, user_ids: list[UUID]) -> None:
        await (
            self._session.update(AuthUser)
            .values(is_deleted=False, delete_reason=None)
            .where(AuthUser.id.in_(user_ids))
            .execute()
        )

    async def get_user_role_ids(self, user_id: UUID) -> list[UUID]:
        return await (
            self._session.select(AuthUserRole.role_id)
            .where(AuthUserRole.user_id == user_id)
            .fetchvals()
        )

    async def bind_roles(self, user_id: UUID, role_ids: list[UUID]) -> tuple[list[UUID], list[UUID]]:
        original_roles = await self.get_user_role_ids(user_id)
        new_role_ids = set(role_ids or [])
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
        return insert_role_ids, delete_role_ids

    async def update_password_hash(self, user_id: UUID, password_hash: str) -> None:
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

    async def locale_exists(self, preferred_locale_id: UUID) -> bool:
        locale_id = await (
            self._session.select(SystemLocale.id)
            .where(SystemLocale.id == preferred_locale_id)
            .where(SystemLocale.is_deleted == False)
            .fetchval()
        )
        return bool(locale_id)

    async def update_preferred_locale(self, user_id: UUID, preferred_locale_id: UUID) -> None:
        await (
            self._session.update(AuthUserProfile)
            .where(AuthUserProfile.user_id == user_id)
            .values(preferred_locale_id=preferred_locale_id)
            .execute()
        )

    async def update_last_login_at(self, user_id: UUID, last_login_at: datetime) -> None:
        await (
            self._session.update(AuthUser)
            .where(AuthUser.id == user_id)
            .values(last_login_at=last_login_at)
            .execute()
        )

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
        now = datetime.now(timezone.utc)
        row_id = uuid4()
        serialized_additional_data = json.dumps(additional_data)
        await (
            self._session.insert(AuthUserThirdParty)
            .values(
                id=row_id,
                user_id=user_id,
                provider=provider.value,
                provider_tenant_id=provider_tenant_id,
                provider_uid=provider_uid,
                access_token=access_token,
                refresh_token=refresh_token,
                token_expires_at=token_expires_at,
                additional_data=serialized_additional_data,
                is_deleted=False,
                created_by="oauth",
                updated_by="oauth",
            )
            .on_conflict_do_update(
                index_elements=["user_id", "provider", "provider_uid"],
                set_={
                    "provider_tenant_id": provider_tenant_id,
                    "token_expires_at": token_expires_at,
                    "additional_data": serialized_additional_data,
                    "updated_at": now,
                    "updated_by": "oauth",
                    "is_deleted": False,
                },
            )
            .execute()
        )
