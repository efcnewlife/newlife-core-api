"""
Map between API serializers and application commands/results.
"""
from uuid import UUID

from portal.application.rbac.commands import (
    AssignRolePermissionsCommand,
    BindUserRolesCommand,
    BulkIdsCommand,
    ChangePasswordCommand,
    ChangeResourceParentCommand,
    ChangeResourceSequenceCommand,
    CreateAdminUserCommand,
    CreatePermissionCommand,
    CreateResourceCommand,
    CreateRoleCommand,
    DeleteCommand,
    AdminUserPagesQueryCommand,
    PagesQueryCommand,
    PermissionPagesQueryCommand,
    ResourceListQueryCommand,
    TranslationCommand,
    UpdateAdminUserCommand,
    UpdatePermissionCommand,
    UpdateResourceCommand,
    UpdateRoleCommand,
)
from portal.application.rbac.results import (
    AdminUserDetailResult,
    AdminUserListResult,
    AdminUserPageResult,
    AdminUserRolesResult,
    CreateIdResult,
    PermissionDetailResult,
    PermissionListResult,
    PermissionPageResult,
    ResourceDetailResult,
    ResourceListResult,
    ResourceTreeResult,
    RoleDetailResult,
    RoleListResult,
    RolePageResult,
    VerbListResult,
)
from portal.serializers.mixins.model_mixins import UUIDBaseModel
from portal.serializers.admin.v1.permission import (
    AdminPermissionBulkAction,
    AdminPermissionCreate,
    AdminPermissionDetail,
    AdminPermissionItem,
    AdminPermissionList,
    AdminPermissionPage,
    AdminPermissionQuery,
    AdminPermissionUpdate,
)
from portal.serializers.admin.v1.resource import (
    AdminResourceChangeParent,
    AdminResourceChangeSequence,
    AdminResourceCreate,
    AdminResourceDetail,
    AdminResourceItem,
    AdminResourceList,
    AdminResourceTree,
    AdminResourceTreeItem,
    AdminResourceUpdate,
)
from portal.serializers.admin.v1.role import (
    AdminRoleCreate,
    AdminRoleList,
    AdminRolePages,
    AdminRolePermissionAssign,
    AdminRoleTableItem,
    AdminRoleUpdate,
)
from portal.serializers.admin.v1.user import (
    AdminBindRole,
    AdminChangePassword,
    AdminUserBulkAction,
    AdminUserCreate,
    AdminUserItem,
    AdminUserList,
    AdminUserPages,
    AdminUserQuery,
    AdminUserRoles,
    AdminUserUpdate,
)
from portal.serializers.admin.v1.translation import AdminTranslationInput
from portal.serializers.admin.v1.verb import AdminVerbItem, AdminVerbList
from portal.serializers.mixins import DeleteBaseModel, GenericQueryBaseModel
from portal.serializers.mixins.base import DeleteQueryBaseModel


def _translation_commands(translations: list[AdminTranslationInput] | None) -> list[TranslationCommand] | None:
    if translations is None:
        return None
    return [
        TranslationCommand(
            locale_id=item.locale_id,
            name=item.name,
            description=item.description,
            remark=item.remark,
        )
        for item in translations
    ]


def pages_query_to_command(model: GenericQueryBaseModel) -> PagesQueryCommand:
    return PagesQueryCommand(
        page=model.page,
        page_size=model.page_size,
        order_by=model.order_by,
        descending=model.descending,
        deleted=model.deleted,
        keyword=model.keyword,
    )


def admin_user_pages_query_to_command(model: AdminUserQuery) -> AdminUserPagesQueryCommand:
    return AdminUserPagesQueryCommand(
        page=model.page,
        page_size=model.page_size,
        order_by=model.order_by,
        descending=model.descending,
        deleted=model.deleted,
        keyword=model.keyword,
        verified=model.verified,
        is_active=model.is_active,
        is_superuser=model.is_superuser,
        is_admin=model.is_admin,
        is_ministry=model.is_ministry,
        gender=model.gender,
    )


def delete_model_to_command(model: DeleteBaseModel) -> DeleteCommand:
    return DeleteCommand(reason=model.reason, permanent=model.permanent)


def create_role_to_command(model: AdminRoleCreate) -> CreateRoleCommand:
    return CreateRoleCommand(
        code=model.code,
        name=model.name,
        is_active=model.is_active,
        description=model.description,
        remark=model.remark,
        permissions=model.permissions,
        translations=_translation_commands(model.translations),
    )


def update_role_to_command(model: AdminRoleUpdate) -> UpdateRoleCommand:
    return UpdateRoleCommand(
        code=model.code,
        name=model.name,
        is_active=model.is_active,
        description=model.description,
        remark=model.remark,
        permissions=model.permissions,
        translations=_translation_commands(model.translations),
    )


def assign_role_permissions_to_command(model: AdminRolePermissionAssign) -> AssignRolePermissionsCommand:
    return AssignRolePermissionsCommand(permission_ids=model.permission_ids)


def create_resource_to_command(model: AdminResourceCreate) -> CreateResourceCommand:
    return CreateResourceCommand(
        pid=model.pid,
        name=model.name,
        key=model.key,
        code=model.code,
        icon=model.icon,
        path=model.path,
        type=model.type,
        is_visible=model.is_visible,
        description=model.description,
        remark=model.remark,
        translations=_translation_commands(model.translations),
    )


def update_resource_to_command(model: AdminResourceUpdate) -> UpdateResourceCommand:
    return UpdateResourceCommand(
        pid=model.pid,
        name=model.name,
        key=model.key,
        code=model.code,
        icon=model.icon,
        path=model.path,
        type=model.type,
        is_visible=model.is_visible,
        description=model.description,
        remark=model.remark,
        translations=_translation_commands(model.translations),
    )


def change_resource_parent_to_command(model: AdminResourceChangeParent) -> ChangeResourceParentCommand:
    return ChangeResourceParentCommand(pid=model.pid)


def change_resource_sequence_to_command(model: AdminResourceChangeSequence) -> ChangeResourceSequenceCommand:
    return ChangeResourceSequenceCommand(
        id=model.id,
        sequence=model.sequence,
        another_id=model.another_id,
        another_sequence=model.another_sequence,
    )


def resource_list_query_to_command(model: DeleteQueryBaseModel) -> ResourceListQueryCommand:
    return ResourceListQueryCommand(deleted=model.deleted)


def create_admin_user_to_command(model: AdminUserCreate) -> CreateAdminUserCommand:
    return CreateAdminUserCommand(
        phone_number=model.phone_number,
        email=model.email,
        verified=model.verified,
        is_active=model.is_active,
        is_superuser=model.is_superuser,
        is_admin=model.is_admin,
        display_name=model.display_name,
        gender=model.gender,
        is_ministry=model.is_ministry,
        remark=model.remark,
        password=model.password,
        password_confirm=model.password_confirm,
    )


def update_admin_user_to_command(model: AdminUserUpdate) -> UpdateAdminUserCommand:
    return UpdateAdminUserCommand(
        phone_number=model.phone_number,
        email=model.email,
        verified=model.verified,
        is_active=model.is_active,
        is_superuser=model.is_superuser,
        is_admin=model.is_admin,
        display_name=model.display_name,
        gender=model.gender,
        is_ministry=model.is_ministry,
        remark=model.remark,
    )


def change_password_to_command(model: AdminChangePassword) -> ChangePasswordCommand:
    return ChangePasswordCommand(
        old_password=model.old_password,
        new_password=model.new_password,
        new_password_confirm=model.new_password_confirm,
    )


def bind_user_roles_to_command(model: AdminBindRole) -> BindUserRolesCommand:
    return BindUserRolesCommand(role_ids=model.role_ids or [])


def bulk_ids_to_command(model: AdminUserBulkAction) -> BulkIdsCommand:
    return BulkIdsCommand(ids=model.ids)


def verb_list_result_to_api(result: VerbListResult) -> AdminVerbList:
    items = [
        AdminVerbItem(
            id=item.id,
            action=item.action,
            name=item.name,
            description=item.description,
        )
        for item in result.items
    ]
    return AdminVerbList(items=items or None)


def role_page_result_to_api(result: RolePageResult) -> AdminRolePages:
    items = [AdminRoleTableItem.model_validate(item.model_dump()) for item in result.items]
    return AdminRolePages(
        page=result.page,
        page_size=result.page_size,
        total=result.total,
        items=items or None,
    )


def role_list_result_to_api(result: RoleListResult) -> AdminRoleList:
    from portal.serializers.admin.v1.role import AdminRoleBase

    items = [AdminRoleBase.model_validate(item.model_dump()) for item in result.items]
    return AdminRoleList(items=items or None)


def role_detail_result_to_api(result: RoleDetailResult) -> AdminRoleTableItem:
    return AdminRoleTableItem.model_validate(result.model_dump())


def resource_detail_result_to_api(result: ResourceDetailResult) -> AdminResourceDetail:
    return AdminResourceDetail.model_validate(result.model_dump())


def resource_list_result_to_api(result: ResourceListResult) -> AdminResourceList:
    items = [AdminResourceItem.model_validate(item.model_dump()) for item in result.items]
    return AdminResourceList(items=items or None)


def resource_tree_result_to_api(result: ResourceTreeResult) -> AdminResourceTree:
    items = [AdminResourceTreeItem.model_validate(item.model_dump()) for item in result.items]
    return AdminResourceTree(items=items or None)


def admin_user_page_result_to_api(result: AdminUserPageResult) -> AdminUserPages:
    from portal.serializers.admin.v1.user import AdminUserTableItem

    items = [AdminUserTableItem.model_validate(item.model_dump()) for item in result.items]
    return AdminUserPages(
        page=result.page,
        page_size=result.page_size,
        total=result.total,
        items=items or None,
    )


def admin_user_list_result_to_api(result: AdminUserListResult) -> AdminUserList:
    from portal.serializers.admin.v1.user import AdminUserBase

    items = [AdminUserBase.model_validate(item.model_dump()) for item in result.items]
    return AdminUserList(items=items or None)


def admin_user_detail_result_to_api(result: AdminUserDetailResult) -> AdminUserItem:
    return AdminUserItem.model_validate(result.model_dump())


def admin_user_roles_result_to_api(result: AdminUserRolesResult) -> AdminUserRoles:
    return AdminUserRoles(role_ids=result.role_ids)


def create_id_result_to_api(result: CreateIdResult) -> UUIDBaseModel:
    return UUIDBaseModel(id=result.id)


def permission_pages_query_to_command(model: AdminPermissionQuery) -> PermissionPagesQueryCommand:
    return PermissionPagesQueryCommand(
        page=model.page,
        page_size=model.page_size,
        order_by=model.order_by,
        descending=model.descending,
        deleted=model.deleted,
        keyword=model.keyword,
        is_active=model.is_active,
    )


def create_permission_to_command(model: AdminPermissionCreate) -> CreatePermissionCommand:
    return CreatePermissionCommand(
        code=model.code,
        resource_id=model.resource_id,
        verb_id=model.verb_id,
        is_active=model.is_active,
        name=model.name,
        description=model.description,
        remark=model.remark,
        translations=_translation_commands(model.translations),
    )


def update_permission_to_command(model: AdminPermissionUpdate) -> UpdatePermissionCommand:
    return UpdatePermissionCommand(
        code=model.code,
        resource_id=model.resource_id,
        verb_id=model.verb_id,
        is_active=model.is_active,
        name=model.name,
        description=model.description,
        remark=model.remark,
        translations=_translation_commands(model.translations),
    )


def permission_bulk_action_to_command(model: AdminPermissionBulkAction) -> BulkIdsCommand:
    return BulkIdsCommand(ids=model.ids)


def permission_page_result_to_api(result: PermissionPageResult) -> AdminPermissionPage:
    from portal.serializers.admin.v1.permission import AdminPermissionPageItem

    items = [AdminPermissionPageItem.model_validate(item.model_dump()) for item in result.items]
    return AdminPermissionPage(
        page=result.page,
        page_size=result.page_size,
        total=result.total,
        items=items or None,
    )


def permission_list_result_to_api(result: PermissionListResult) -> AdminPermissionList:
    items = [AdminPermissionItem.model_validate(item.model_dump()) for item in result.items]
    return AdminPermissionList(items=items or None)


def permission_detail_result_to_api(result: PermissionDetailResult) -> AdminPermissionDetail:
    return AdminPermissionDetail.model_validate(result.model_dump())
