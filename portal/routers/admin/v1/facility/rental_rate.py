"""
Admin facility rental rate API routes.
"""
import uuid
from typing import Annotated, Optional

from dependency_injector.wiring import inject, Provide
from fastapi import Depends, HTTPException, Query, status

from portal.application.facility.mappers import (
    create_id_result_to_api,
    create_rental_rate_to_command,
    delete_model_to_command,
    preview_quote_result_to_api,
    preview_quote_to_command,
    rental_rate_list_to_api,
    rental_rate_page_to_api,
    rental_rate_pages_query_to_command,
    rental_rate_to_api,
    update_rental_rate_to_command,
)
from portal.application.facility.pricing_service import PricingService
from portal.application.facility.rental_rate_service import RentalRateService
from portal.container import Container
from portal.libs.consts.permission import Permission
from portal.routers.auth_router import AuthRouter
from portal.serializers.mixins.model_mixins import UUIDBaseModel
from portal.serializers.mixins import DeleteBaseModel, DetailQueryModel
from portal.serializers.admin.v1.facility.rental_rate import (
    AdminPreviewQuoteRequest,
    AdminPreviewQuoteResponse,
    AdminRentalRateCreate,
    AdminRentalRateItem,
    AdminRentalRateList,
    AdminRentalRatePages,
    AdminRentalRateQuery,
    AdminRentalRateUpdate,
)

router: AuthRouter = AuthRouter(is_admin=True)


@router.get(
    path="/pages",
    status_code=status.HTTP_200_OK,
    response_model=AdminRentalRatePages,
    permissions=[Permission.FACILITY_RENTAL_RATE.read],
)
@inject
async def get_rental_rate_pages(
    query_model: Annotated[AdminRentalRateQuery, Query()],
    rental_rate_service: RentalRateService = Depends(Provide[Container.rental_rate_service]),
):
    command, facility_id = rental_rate_pages_query_to_command(query_model)
    result = await rental_rate_service.get_rate_pages(
        command=command,
        facility_id=facility_id,
    )
    return rental_rate_page_to_api(result)


@router.get(
    path="/list",
    status_code=status.HTTP_200_OK,
    response_model=AdminRentalRateList,
    permissions=[Permission.FACILITY_RENTAL_RATE.read],
)
@inject
async def get_rental_rate_list(
    facility_id: Annotated[Optional[uuid.UUID], Query(alias="facilityId")] = None,
    rental_rate_service: RentalRateService = Depends(Provide[Container.rental_rate_service]),
):
    result = await rental_rate_service.get_rate_list(facility_id=facility_id)
    return rental_rate_list_to_api(result)


@router.post(
    path="/preview-quote",
    status_code=status.HTTP_200_OK,
    response_model=AdminPreviewQuoteResponse,
    permissions=[Permission.FACILITY_RENTAL_RATE.read],
)
@inject
async def preview_quote(
    model: AdminPreviewQuoteRequest,
    pricing_service: PricingService = Depends(Provide[Container.pricing_service]),
):
    result = await pricing_service.preview_quote(command=preview_quote_to_command(model))
    return preview_quote_result_to_api(result)


@router.post(
    path="",
    status_code=status.HTTP_201_CREATED,
    response_model=UUIDBaseModel,
    permissions=[Permission.FACILITY_RENTAL_RATE.create],
)
@inject
async def create_rental_rate(
    model: AdminRentalRateCreate,
    rental_rate_service: RentalRateService = Depends(Provide[Container.rental_rate_service]),
):
    result = await rental_rate_service.create_rate(command=create_rental_rate_to_command(model))
    return create_id_result_to_api(result)


@router.get(
    path="/{rate_id}",
    status_code=status.HTTP_200_OK,
    response_model=AdminRentalRateItem,
    permissions=[Permission.FACILITY_RENTAL_RATE.read],
)
@inject
async def get_rental_rate(
    rate_id: uuid.UUID,
    query_model: Annotated[DetailQueryModel, Query()],
    rental_rate_service: RentalRateService = Depends(Provide[Container.rental_rate_service]),
):
    result = await rental_rate_service.get_rate_by_id(
        rate_id=rate_id,
        all_locales=query_model.all_locales,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Rental rate not found")
    return rental_rate_to_api(result)


@router.put(
    path="/{rate_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    permissions=[Permission.FACILITY_RENTAL_RATE.modify],
)
@inject
async def update_rental_rate(
    rate_id: uuid.UUID,
    model: AdminRentalRateUpdate,
    rental_rate_service: RentalRateService = Depends(Provide[Container.rental_rate_service]),
):
    await rental_rate_service.update_rate(rate_id=rate_id, command=update_rental_rate_to_command(model))


@router.delete(
    path="/{rate_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    permissions=[Permission.FACILITY_RENTAL_RATE.delete],
)
@inject
async def delete_rental_rate(
    rate_id: uuid.UUID,
    model: DeleteBaseModel,
    rental_rate_service: RentalRateService = Depends(Provide[Container.rental_rate_service]),
):
    await rental_rate_service.delete_rate(rate_id=rate_id, command=delete_model_to_command(model))


@router.put(
    path="/{rate_id}/restore",
    status_code=status.HTTP_204_NO_CONTENT,
    permissions=[Permission.FACILITY_RENTAL_RATE.modify],
)
@inject
async def restore_rental_rate(
    rate_id: uuid.UUID,
    rental_rate_service: RentalRateService = Depends(Provide[Container.rental_rate_service]),
):
    await rental_rate_service.restore_rate(rate_id=rate_id)
