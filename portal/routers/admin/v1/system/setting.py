"""
Admin system setting API routes.
"""

from typing import Annotated, Optional
from uuid import UUID

from dependency_injector.wiring import Provide, inject
from fastapi import Depends, Query, status

from portal.application.system.mappers import (
    bulk_action_to_command,
    create_setting_to_command,
    delete_model_to_command,
    setting_list_to_api,
    setting_result_to_api,
    update_setting_to_command,
)
from portal.application.system.setting_service import SettingService
from portal.container import Container
from portal.libs.consts.permission import Permission
from portal.routers.auth_router import AuthRouter
from portal.serializers.admin.v1.system.setting import AdminSettingBulkAction, AdminSettingCreate, AdminSettingItem, AdminSettingList, AdminSettingUpdate
from portal.serializers.mixins import DeleteBaseModel
from portal.serializers.mixins.model_mixins import UUIDBaseModel

router: AuthRouter = AuthRouter(is_admin=True)


@router.get(path="/list", status_code=status.HTTP_200_OK, response_model=AdminSettingList, permissions=[Permission.SYSTEM_SETTING.read])
@inject
async def list_settings(
    namespace: Annotated[Optional[str], Query()] = None,
    deleted: Annotated[bool, Query()] = False,
    setting_service: SettingService = Depends(Provide[Container.setting_service]),
):
    result = await setting_service.list_settings(namespace=namespace, deleted=deleted)
    return setting_list_to_api(result)


@router.get(path="/by-key", status_code=status.HTTP_200_OK, response_model=AdminSettingItem, permissions=[Permission.SYSTEM_SETTING.read])
@inject
async def get_setting_by_key(
    namespace: Annotated[str, Query()], setting_key: Annotated[str, Query()], setting_service: SettingService = Depends(Provide[Container.setting_service])
):
    result = await setting_service.get_setting_by_key(namespace=namespace, setting_key=setting_key)
    return setting_result_to_api(result)


@router.post(path="", status_code=status.HTTP_201_CREATED, response_model=UUIDBaseModel, permissions=[Permission.SYSTEM_SETTING.create])
@inject
async def create_setting(body: AdminSettingCreate, setting_service: SettingService = Depends(Provide[Container.setting_service])):
    return await setting_service.create_setting(command=create_setting_to_command(body))


@router.put(path="/restore", status_code=status.HTTP_204_NO_CONTENT, permissions=[Permission.SYSTEM_SETTING.delete])
@inject
async def restore_settings(body: AdminSettingBulkAction, setting_service: SettingService = Depends(Provide[Container.setting_service])):
    await setting_service.restore_settings(command=bulk_action_to_command(body))


@router.get(path="/{setting_id}", status_code=status.HTTP_200_OK, response_model=AdminSettingItem, permissions=[Permission.SYSTEM_SETTING.read])
@inject
async def get_setting(setting_id: UUID, setting_service: SettingService = Depends(Provide[Container.setting_service])):
    result = await setting_service.get_setting_by_id(setting_id)
    return setting_result_to_api(result)


@router.put(path="/{setting_id}", status_code=status.HTTP_200_OK, response_model=AdminSettingItem, permissions=[Permission.SYSTEM_SETTING.modify])
@inject
async def update_setting(setting_id: UUID, body: AdminSettingUpdate, setting_service: SettingService = Depends(Provide[Container.setting_service])):
    result = await setting_service.update_setting(setting_id=setting_id, command=update_setting_to_command(body))
    return setting_result_to_api(result)


@router.delete(path="/{setting_id}", status_code=status.HTTP_204_NO_CONTENT, permissions=[Permission.SYSTEM_SETTING.delete])
@inject
async def delete_setting(setting_id: UUID, body: DeleteBaseModel, setting_service: SettingService = Depends(Provide[Container.setting_service])):
    await setting_service.delete_setting(setting_id=setting_id, command=delete_model_to_command(body))
