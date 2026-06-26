"""
Admin facility rental catalog API routes.
"""
import uuid
from typing import Annotated, Optional

from dependency_injector.wiring import inject, Provide
from fastapi import Depends, Query, status

from portal.application.facility.mappers import (
    create_discount_rule_to_command,
    create_id_result_to_api,
    create_surcharge_to_command,
    delete_model_to_command,
    discount_rule_list_to_api,
    discount_rule_to_api,
    policy_setting_list_to_api,
    policy_setting_to_api,
    surcharge_list_to_api,
    surcharge_to_api,
    update_discount_rule_to_command,
    update_policy_setting_to_command,
    update_surcharge_to_command,
)
from portal.application.facility.rental_catalog_service import RentalCatalogService
from portal.container import Container
from portal.libs.consts.permission import Permission
from portal.routers.auth_router import AuthRouter
from portal.serializers.mixins.model_mixins import UUIDBaseModel
from portal.serializers.mixins import DeleteBaseModel
from portal.serializers.admin.v1.facility.rental_catalog import (
    AdminDiscountRuleCreate,
    AdminDiscountRuleItem,
    AdminDiscountRuleList,
    AdminDiscountRuleUpdate,
    AdminPolicySettingItem,
    AdminPolicySettingList,
    AdminPolicySettingUpdate,
    AdminSurchargeCreate,
    AdminSurchargeItem,
    AdminSurchargeList,
    AdminSurchargeUpdate,
)

router: AuthRouter = AuthRouter(is_admin=True)


@router.get(
    path="/discount-rules",
    status_code=status.HTTP_200_OK,
    response_model=AdminDiscountRuleList,
    permissions=[Permission.FACILITY_RENTAL_RATE.read],
)
@inject
async def list_discount_rules(
    rental_catalog_service: RentalCatalogService = Depends(Provide[Container.rental_catalog_service]),
):
    result = await rental_catalog_service.list_discount_rules()
    return discount_rule_list_to_api(result)


@router.post(
    path="/discount-rules",
    status_code=status.HTTP_201_CREATED,
    response_model=UUIDBaseModel,
    permissions=[Permission.FACILITY_RENTAL_RATE.create],
)
@inject
async def create_discount_rule(
    model: AdminDiscountRuleCreate,
    rental_catalog_service: RentalCatalogService = Depends(Provide[Container.rental_catalog_service]),
):
    result = await rental_catalog_service.create_discount_rule(
        command=create_discount_rule_to_command(model)
    )
    return create_id_result_to_api(result)


@router.get(
    path="/discount-rules/{rule_id}",
    status_code=status.HTTP_200_OK,
    response_model=AdminDiscountRuleItem,
    permissions=[Permission.FACILITY_RENTAL_RATE.read],
)
@inject
async def get_discount_rule(
    rule_id: uuid.UUID,
    rental_catalog_service: RentalCatalogService = Depends(Provide[Container.rental_catalog_service]),
):
    return discount_rule_to_api(await rental_catalog_service.get_discount_rule(rule_id))


@router.put(
    path="/discount-rules/{rule_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    permissions=[Permission.FACILITY_RENTAL_RATE.modify],
)
@inject
async def update_discount_rule(
    rule_id: uuid.UUID,
    model: AdminDiscountRuleUpdate,
    rental_catalog_service: RentalCatalogService = Depends(Provide[Container.rental_catalog_service]),
):
    await rental_catalog_service.update_discount_rule(
        rule_id=rule_id,
        command=update_discount_rule_to_command(model),
    )


@router.delete(
    path="/discount-rules/{rule_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    permissions=[Permission.FACILITY_RENTAL_RATE.delete],
)
@inject
async def delete_discount_rule(
    rule_id: uuid.UUID,
    model: DeleteBaseModel,
    rental_catalog_service: RentalCatalogService = Depends(Provide[Container.rental_catalog_service]),
):
    await rental_catalog_service.delete_discount_rule(
        rule_id=rule_id,
        command=delete_model_to_command(model),
    )


@router.get(
    path="/surcharges",
    status_code=status.HTTP_200_OK,
    response_model=AdminSurchargeList,
    permissions=[Permission.FACILITY_RENTAL_RATE.read],
)
@inject
async def list_surcharges(
    rental_catalog_service: RentalCatalogService = Depends(Provide[Container.rental_catalog_service]),
):
    result = await rental_catalog_service.list_surcharges()
    return surcharge_list_to_api(result)


@router.post(
    path="/surcharges",
    status_code=status.HTTP_201_CREATED,
    response_model=UUIDBaseModel,
    permissions=[Permission.FACILITY_RENTAL_RATE.create],
)
@inject
async def create_surcharge(
    model: AdminSurchargeCreate,
    rental_catalog_service: RentalCatalogService = Depends(Provide[Container.rental_catalog_service]),
):
    result = await rental_catalog_service.create_surcharge(command=create_surcharge_to_command(model))
    return create_id_result_to_api(result)


@router.get(
    path="/surcharges/{surcharge_id}",
    status_code=status.HTTP_200_OK,
    response_model=AdminSurchargeItem,
    permissions=[Permission.FACILITY_RENTAL_RATE.read],
)
@inject
async def get_surcharge(
    surcharge_id: uuid.UUID,
    rental_catalog_service: RentalCatalogService = Depends(Provide[Container.rental_catalog_service]),
):
    return surcharge_to_api(await rental_catalog_service.get_surcharge(surcharge_id))


@router.put(
    path="/surcharges/{surcharge_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    permissions=[Permission.FACILITY_RENTAL_RATE.modify],
)
@inject
async def update_surcharge(
    surcharge_id: uuid.UUID,
    model: AdminSurchargeUpdate,
    rental_catalog_service: RentalCatalogService = Depends(Provide[Container.rental_catalog_service]),
):
    await rental_catalog_service.update_surcharge(
        surcharge_id=surcharge_id,
        command=update_surcharge_to_command(model),
    )


@router.delete(
    path="/surcharges/{surcharge_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    permissions=[Permission.FACILITY_RENTAL_RATE.delete],
)
@inject
async def delete_surcharge(
    surcharge_id: uuid.UUID,
    model: DeleteBaseModel,
    rental_catalog_service: RentalCatalogService = Depends(Provide[Container.rental_catalog_service]),
):
    await rental_catalog_service.delete_surcharge(
        surcharge_id=surcharge_id,
        command=delete_model_to_command(model),
    )


@router.get(
    path="/policy-settings",
    status_code=status.HTTP_200_OK,
    response_model=AdminPolicySettingList,
    permissions=[Permission.FACILITY_RENTAL_RATE.read],
)
@inject
async def list_policy_settings(
    facility_id: Annotated[Optional[uuid.UUID], Query(alias="facilityId")] = None,
    rental_catalog_service: RentalCatalogService = Depends(Provide[Container.rental_catalog_service]),
):
    result = await rental_catalog_service.list_policy_settings(facility_id=facility_id)
    return policy_setting_list_to_api(result)


@router.get(
    path="/policy-settings/{setting_id}",
    status_code=status.HTTP_200_OK,
    response_model=AdminPolicySettingItem,
    permissions=[Permission.FACILITY_RENTAL_RATE.read],
)
@inject
async def get_policy_setting(
    setting_id: uuid.UUID,
    rental_catalog_service: RentalCatalogService = Depends(Provide[Container.rental_catalog_service]),
):
    return policy_setting_to_api(await rental_catalog_service.get_policy_setting(setting_id))


@router.put(
    path="/policy-settings/{setting_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    permissions=[Permission.FACILITY_RENTAL_RATE.modify],
)
@inject
async def update_policy_setting(
    setting_id: uuid.UUID,
    model: AdminPolicySettingUpdate,
    rental_catalog_service: RentalCatalogService = Depends(Provide[Container.rental_catalog_service]),
):
    await rental_catalog_service.update_policy_setting(
        setting_id=setting_id,
        command=update_policy_setting_to_command(model),
    )
