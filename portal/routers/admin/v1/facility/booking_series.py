"""
Admin Recurring Booking Series API routes.
"""

from dependency_injector.wiring import Provide, inject
from fastapi import Depends, status

from portal.application.facility.mappers import create_recurring_booking_series_to_command, recurring_booking_series_to_admin_api
from portal.application.facility.recurring_booking_service import RecurringBookingService
from portal.container import Container
from portal.libs.consts.permission import Permission
from portal.routers.auth_router import AuthRouter
from portal.serializers.admin.v1.facility.booking_series import AdminRecurringBookingSeriesCreate, AdminRecurringBookingSeriesDetail

router: AuthRouter = AuthRouter(is_admin=True)


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
