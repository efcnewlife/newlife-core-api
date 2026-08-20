"""
Admin facility rental rate template API routes.
"""

import uuid
from typing import Annotated

from dependency_injector.wiring import Provide, inject
from fastapi import Depends, Query, status

from portal.application.facility.mappers import (
    create_id_result_to_api,
    create_rental_rate_template_to_command,
    delete_model_to_command,
    pages_query_to_command,
    rental_rate_template_list_to_api,
    rental_rate_template_page_to_api,
    rental_rate_template_to_api,
    update_rental_rate_template_to_command,
)
from portal.application.facility.rental_rate_template_service import RentalRateTemplateService
from portal.container import Container
from portal.domain.facility.constants import FacilityErrorCode
from portal.exceptions.responses import NotFoundException
from portal.libs.consts.permission import Permission
from portal.routers.auth_router import AuthRouter
from portal.serializers.admin.v1.facility.rental_rate_template import (
    AdminRentalRateTemplateCreate,
    AdminRentalRateTemplateItem,
    AdminRentalRateTemplateList,
    AdminRentalRateTemplatePages,
    AdminRentalRateTemplateQuery,
    AdminRentalRateTemplateUpdate,
)
from portal.serializers.mixins import DeleteBaseModel
from portal.serializers.mixins.model_mixins import UUIDBaseModel

router: AuthRouter = AuthRouter(is_admin=True)


@router.get(
    path="/pages", status_code=status.HTTP_200_OK, response_model=AdminRentalRateTemplatePages, permissions=[Permission.FACILITY_RENTAL_RATE_TEMPLATE.read]
)
@inject
async def get_rental_rate_template_pages(
    query_model: Annotated[AdminRentalRateTemplateQuery, Query()],
    rental_rate_template_service: RentalRateTemplateService = Depends(Provide[Container.rental_rate_template_service]),
):
    result = await rental_rate_template_service.get_template_pages(command=pages_query_to_command(query_model))
    return rental_rate_template_page_to_api(result)


@router.get(
    path="/list", status_code=status.HTTP_200_OK, response_model=AdminRentalRateTemplateList, permissions=[Permission.FACILITY_RENTAL_RATE_TEMPLATE.read]
)
@inject
async def get_rental_rate_template_list(rental_rate_template_service: RentalRateTemplateService = Depends(Provide[Container.rental_rate_template_service])):
    result = await rental_rate_template_service.get_template_list()
    return rental_rate_template_list_to_api(result)


@router.post(path="", status_code=status.HTTP_201_CREATED, response_model=UUIDBaseModel, permissions=[Permission.FACILITY_RENTAL_RATE_TEMPLATE.create])
@inject
async def create_rental_rate_template(
    model: AdminRentalRateTemplateCreate, rental_rate_template_service: RentalRateTemplateService = Depends(Provide[Container.rental_rate_template_service])
):
    result = await rental_rate_template_service.create_template(command=create_rental_rate_template_to_command(model))
    return create_id_result_to_api(result)


@router.get(
    path="/{template_id}",
    status_code=status.HTTP_200_OK,
    response_model=AdminRentalRateTemplateItem,
    permissions=[Permission.FACILITY_RENTAL_RATE_TEMPLATE.read],
)
@inject
async def get_rental_rate_template(
    template_id: uuid.UUID, rental_rate_template_service: RentalRateTemplateService = Depends(Provide[Container.rental_rate_template_service])
):
    result = await rental_rate_template_service.get_template_by_id(template_id=template_id)
    if not result:
        raise NotFoundException(
            detail="Rental rate template not found",
            error_code=FacilityErrorCode.RENTAL_RATE_TEMPLATE_NOT_FOUND.value,
            context={"template_id": str(template_id)},
        )
    return rental_rate_template_to_api(result)


@router.put(path="/{template_id}", status_code=status.HTTP_204_NO_CONTENT, permissions=[Permission.FACILITY_RENTAL_RATE_TEMPLATE.modify])
@inject
async def update_rental_rate_template(
    template_id: uuid.UUID,
    model: AdminRentalRateTemplateUpdate,
    rental_rate_template_service: RentalRateTemplateService = Depends(Provide[Container.rental_rate_template_service]),
):
    await rental_rate_template_service.update_template(template_id=template_id, command=update_rental_rate_template_to_command(model))


@router.delete(path="/{template_id}", status_code=status.HTTP_204_NO_CONTENT, permissions=[Permission.FACILITY_RENTAL_RATE_TEMPLATE.delete])
@inject
async def delete_rental_rate_template(
    template_id: uuid.UUID,
    model: DeleteBaseModel,
    rental_rate_template_service: RentalRateTemplateService = Depends(Provide[Container.rental_rate_template_service]),
):
    await rental_rate_template_service.delete_template(template_id=template_id, command=delete_model_to_command(model))


@router.put(path="/{template_id}/restore", status_code=status.HTTP_204_NO_CONTENT, permissions=[Permission.FACILITY_RENTAL_RATE_TEMPLATE.modify])
@inject
async def restore_rental_rate_template(
    template_id: uuid.UUID, rental_rate_template_service: RentalRateTemplateService = Depends(Provide[Container.rental_rate_template_service])
):
    await rental_rate_template_service.restore_template(template_id=template_id)
