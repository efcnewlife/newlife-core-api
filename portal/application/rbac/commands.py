"""
RBAC application commands (snake_case, no API serialization aliases).
"""
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from portal.libs.consts.enums import Gender, ResourceType


class TranslationCommand(BaseModel):
    """Localized content for create/update payloads."""

    locale_id: UUID = Field(...)
    name: str = Field(...)
    description: Optional[str] = Field(default=None)
    remark: Optional[str] = Field(default=None)


class PagesQueryCommand(BaseModel):
    """Paginated list query."""

    page: int = Field(default=0)
    page_size: int = Field(default=10)
    order_by: Optional[str] = Field(default=None)
    descending: bool = Field(default=False)
    deleted: bool = Field(default=False)
    keyword: Optional[str] = Field(default=None)


class DeleteCommand(BaseModel):
    """Soft or permanent delete."""

    reason: Optional[str] = Field(default=None)
    permanent: bool = Field(default=False)


class BulkIdsCommand(BaseModel):
    """Bulk action by ids."""

    ids: list[UUID] = Field(default_factory=list)


class CreateRoleCommand(BaseModel):
    """Create role command."""

    code: str = Field(...)
    name: Optional[str] = Field(default=None)
    is_active: bool = Field(default=True)
    description: Optional[str] = Field(default=None)
    remark: Optional[str] = Field(default=None)
    permissions: list[UUID] = Field(default_factory=list)
    translations: Optional[list[TranslationCommand]] = Field(default=None)

    @model_validator(mode="after")
    def validate_legacy_or_translations(self):
        if self.translations or self.name:
            return self
        raise ValueError("Either translations or name is required")


class UpdateRoleCommand(BaseModel):
    """Update role command."""

    code: str = Field(...)
    name: Optional[str] = Field(default=None)
    is_active: bool = Field(default=True)
    description: Optional[str] = Field(default=None)
    remark: Optional[str] = Field(default=None)
    permissions: list[UUID] = Field(default_factory=list)
    translations: Optional[list[TranslationCommand]] = Field(default=None)


class AssignRolePermissionsCommand(BaseModel):
    """Assign permissions to a role."""

    permission_ids: list[UUID] = Field(default_factory=list)


class CreateResourceCommand(BaseModel):
    """Create resource command."""

    pid: Optional[UUID] = Field(default=None)
    name: Optional[str] = Field(default=None)
    key: str = Field(...)
    code: str = Field(...)
    icon: str = Field(...)
    path: str = Field(...)
    type: ResourceType = Field(...)
    is_visible: bool = Field(default=True)
    description: Optional[str] = Field(default=None)
    remark: Optional[str] = Field(default=None)
    translations: Optional[list[TranslationCommand]] = Field(default=None)

    @model_validator(mode="after")
    def validate_legacy_or_translations(self):
        if self.translations or self.name:
            return self
        raise ValueError("Either translations or name is required")


class UpdateResourceCommand(BaseModel):
    """Update resource command."""

    pid: Optional[UUID] = Field(default=None)
    name: Optional[str] = Field(default=None)
    key: str = Field(...)
    code: str = Field(...)
    icon: str = Field(...)
    path: str = Field(...)
    type: ResourceType = Field(...)
    is_visible: bool = Field(default=True)
    description: Optional[str] = Field(default=None)
    remark: Optional[str] = Field(default=None)
    translations: Optional[list[TranslationCommand]] = Field(default=None)


class ChangeResourceParentCommand(BaseModel):
    """Change resource parent."""

    pid: UUID = Field(...)


class ChangeResourceSequenceCommand(BaseModel):
    """Swap resource sequence values."""

    id: UUID = Field(...)
    sequence: float = Field(...)
    another_id: UUID = Field(...)
    another_sequence: float = Field(...)


class ResourceListQueryCommand(BaseModel):
    """Resource list filtered by deleted flag."""

    deleted: bool = Field(default=False)


class AdminUserPagesQueryCommand(PagesQueryCommand):
    """Admin user paginated query."""

    verified: Optional[bool] = Field(default=None)
    is_active: Optional[bool] = Field(default=None)
    is_superuser: Optional[bool] = Field(default=None)
    is_admin: Optional[bool] = Field(default=None)
    is_ministry: Optional[bool] = Field(default=None)
    gender: Optional[Gender] = Field(default=None)


class CreateAdminUserCommand(BaseModel):
    """Create admin user command."""

    phone_number: Optional[str] = Field(default=None)
    email: str = Field(...)
    verified: bool = Field(default=False)
    is_active: bool = Field(default=True)
    is_superuser: bool = Field(default=False)
    is_admin: bool = Field(default=False)
    display_name: Optional[str] = Field(default=None)
    gender: Optional[Gender] = Field(default=Gender.UNKNOWN)
    is_ministry: bool = Field(default=False)
    remark: Optional[str] = Field(default=None)
    password: str = Field(...)
    password_confirm: str = Field(...)


class UpdateAdminUserCommand(BaseModel):
    """Update admin user command."""

    phone_number: Optional[str] = Field(default=None)
    email: str = Field(...)
    verified: bool = Field(default=False)
    is_active: bool = Field(default=True)
    is_superuser: bool = Field(default=False)
    is_admin: bool = Field(default=False)
    display_name: Optional[str] = Field(default=None)
    gender: Optional[Gender] = Field(default=Gender.UNKNOWN)
    is_ministry: bool = Field(default=False)
    remark: Optional[str] = Field(default=None)


class ChangePasswordCommand(BaseModel):
    """Change password command."""

    old_password: str = Field(...)
    new_password: str = Field(...)
    new_password_confirm: str = Field(...)


class BindUserRolesCommand(BaseModel):
    """Bind roles to a user."""

    role_ids: list[UUID] = Field(default_factory=list)


class PermissionPagesQueryCommand(PagesQueryCommand):
    """Permission paginated query."""

    is_active: Optional[bool] = Field(default=None)


class CreatePermissionCommand(BaseModel):
    """Create permission command."""

    code: str = Field(...)
    resource_id: UUID = Field(...)
    verb_id: UUID = Field(...)
    is_active: bool = Field(default=True)
    name: Optional[str] = Field(default=None)
    description: Optional[str] = Field(default=None)
    remark: Optional[str] = Field(default=None)
    translations: Optional[list[TranslationCommand]] = Field(default=None)

    @model_validator(mode="after")
    def validate_legacy_or_translations(self):
        if self.translations or self.name:
            return self
        raise ValueError("Either translations or name is required")


class UpdatePermissionCommand(BaseModel):
    """Update permission command."""

    code: str = Field(...)
    resource_id: UUID = Field(...)
    verb_id: UUID = Field(...)
    is_active: bool = Field(default=True)
    name: Optional[str] = Field(default=None)
    description: Optional[str] = Field(default=None)
    remark: Optional[str] = Field(default=None)
    translations: Optional[list[TranslationCommand]] = Field(default=None)
