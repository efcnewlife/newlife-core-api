"""
System setting application mappers (API boundary).
"""
from portal.application.rbac.commands import BulkIdsCommand, DeleteCommand
from portal.application.system.commands import CreateSettingCommand, UpdateSettingCommand
from portal.application.system.results import SettingListResult, SettingResult
from portal.serializers.admin.v1.system.setting import (
    AdminSettingBulkAction,
    AdminSettingCreate,
    AdminSettingItem,
    AdminSettingList,
    AdminSettingUpdate,
)
from portal.serializers.mixins import DeleteBaseModel


def create_setting_to_command(model: AdminSettingCreate) -> CreateSettingCommand:
    return CreateSettingCommand(
        namespace=model.namespace,
        setting_key=model.setting_key,
        value_type=model.value_type,
        value=model.value,
        remark=model.remark,
        is_active=model.is_active,
    )


def update_setting_to_command(model: AdminSettingUpdate) -> UpdateSettingCommand:
    return UpdateSettingCommand(value=model.value, remark=model.remark)


def delete_model_to_command(model: DeleteBaseModel) -> DeleteCommand:
    return DeleteCommand(reason=model.reason, permanent=model.permanent)


def bulk_action_to_command(model: AdminSettingBulkAction) -> BulkIdsCommand:
    return BulkIdsCommand(ids=model.ids)


def setting_result_to_api(result: SettingResult) -> AdminSettingItem:
    return AdminSettingItem.model_validate(result.model_dump())


def setting_list_to_api(result: SettingListResult) -> AdminSettingList:
    return AdminSettingList(items=[setting_result_to_api(item) for item in result.items])
