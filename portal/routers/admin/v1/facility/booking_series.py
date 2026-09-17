"""
Admin Recurring Booking Series API routes.
"""

from uuid import UUID

from dependency_injector.wiring import Provide, inject
from fastapi import Depends, status

from portal.application.facility.mappers import (
    create_recurring_booking_series_to_command,
    recurring_booking_preview_to_admin_api,
    recurring_booking_series_to_admin_api,
)
from portal.application.facility.recurring_booking_service import RecurringBookingService
from portal.container import Container
from portal.libs.consts.permission import Permission
from portal.routers.auth_router import AuthRouter
from portal.serializers.admin.v1.facility.booking_series import (
    AdminRecurringBookingPreview,
    AdminRecurringBookingSeriesCreate,
    AdminRecurringBookingSeriesDetail,
    AdminRecurringBookingSeriesProposal,
)

router: AuthRouter = AuthRouter(is_admin=True)


@router.post(
    path="/preview",
    status_code=status.HTTP_200_OK,
    response_model=AdminRecurringBookingPreview,
    response_model_by_alias=True,
    permissions=[Permission.FACILITY_BOOKING.create],
)
@inject
async def preview_booking_series(
    body: AdminRecurringBookingSeriesProposal, recurring_booking_service: RecurringBookingService = Depends(Provide[Container.recurring_booking_service])
):
    result = await recurring_booking_service.preview_conflicts(create_recurring_booking_series_to_command(body))
    return recurring_booking_preview_to_admin_api(result)


@router.post(
    path="",
    status_code=status.HTTP_201_CREATED,
    response_model=AdminRecurringBookingSeriesDetail,
    response_model_by_alias=True,
    permissions=[Permission.FACILITY_BOOKING.create],
)
@inject
async def create_booking_series(
    body: AdminRecurringBookingSeriesCreate, recurring_booking_service: RecurringBookingService = Depends(Provide[Container.recurring_booking_service])
):
    result = await recurring_booking_service.create_series(create_recurring_booking_series_to_command(body))
    return recurring_booking_series_to_admin_api(result)


@router.post(
    path="/{series_id}/confirm-payment",
    status_code=status.HTTP_200_OK,
    response_model=AdminRecurringBookingSeriesDetail,
    response_model_by_alias=True,
    permissions=[Permission.FACILITY_BOOKING_PAYMENT.modify],
)
@inject
async def confirm_booking_series_payment(
    series_id: UUID, recurring_booking_service: RecurringBookingService = Depends(Provide[Container.recurring_booking_service])
):
    result = await recurring_booking_service.confirm_payment(series_id)
    return recurring_booking_series_to_admin_api(result)
