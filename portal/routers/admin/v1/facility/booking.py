"""
Admin facility booking API routes.
"""
import uuid
from typing import Annotated

from dependency_injector.wiring import inject, Provide
from fastapi import Depends, Query, status

from portal.application.facility.booking_service import BookingService
from portal.application.facility.mappers import (
    booking_detail_to_api,
    booking_page_to_api,
    booking_pages_query_to_command,
    cancel_booking_to_command,
    create_booking_to_command,
    create_id_result_to_api,
    update_booking_to_command,
)
from portal.container import Container
from portal.libs.consts.permission import Permission
from portal.routers.auth_router import AuthRouter
from portal.serializers.admin.v1.facility.booking import (
    AdminBookingCancel,
    AdminBookingCreate,
    AdminBookingDetail,
    AdminBookingPages,
    AdminBookingQuery,
    AdminBookingUpdate,
)
from portal.serializers.mixins.model_mixins import UUIDBaseModel

router: AuthRouter = AuthRouter(is_admin=True)


@router.get(
    path="/pages",
    status_code=status.HTTP_200_OK,
    response_model=AdminBookingPages,
    permissions=[Permission.FACILITY_BOOKING.read],
)
@inject
async def get_booking_pages(
    query_model: Annotated[AdminBookingQuery, Query()],
    booking_service: BookingService = Depends(Provide[Container.booking_service]),
):
    result = await booking_service.get_booking_pages(command=booking_pages_query_to_command(query_model))
    return booking_page_to_api(result)


@router.post(
    path="",
    status_code=status.HTTP_201_CREATED,
    response_model=UUIDBaseModel,
    permissions=[Permission.FACILITY_BOOKING.create],
)
@inject
async def create_booking(
    body: AdminBookingCreate,
    booking_service: BookingService = Depends(Provide[Container.booking_service]),
):
    result = await booking_service.create_booking(command=create_booking_to_command(body))
    return create_id_result_to_api(result)


@router.get(
    path="/{booking_id}",
    status_code=status.HTTP_200_OK,
    response_model=AdminBookingDetail,
    permissions=[Permission.FACILITY_BOOKING.read],
)
@inject
async def get_booking_detail(
    booking_id: uuid.UUID,
    booking_service: BookingService = Depends(Provide[Container.booking_service]),
):
    result = await booking_service.get_booking_by_id(booking_id)
    return booking_detail_to_api(result)


@router.put(
    path="/{booking_id}",
    status_code=status.HTTP_200_OK,
    response_model=AdminBookingDetail,
    permissions=[Permission.FACILITY_BOOKING.modify],
)
@inject
async def update_booking(
    booking_id: uuid.UUID,
    body: AdminBookingUpdate,
    booking_service: BookingService = Depends(Provide[Container.booking_service]),
):
    result = await booking_service.update_booking(
        booking_id=booking_id,
        command=update_booking_to_command(body),
    )
    return booking_detail_to_api(result)


@router.post(
    path="/{booking_id}/cancel",
    status_code=status.HTTP_204_NO_CONTENT,
    permissions=[Permission.FACILITY_BOOKING.modify],
)
@inject
async def cancel_booking(
    booking_id: uuid.UUID,
    body: AdminBookingCancel,
    booking_service: BookingService = Depends(Provide[Container.booking_service]),
):
    await booking_service.cancel_booking(booking_id=booking_id, command=cancel_booking_to_command(body))
