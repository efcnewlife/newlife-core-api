"""
Member facility API routes (availability + bookings).
"""

from datetime import date
from typing import Optional
from uuid import UUID

from dependency_injector.wiring import Provide, inject
from fastapi import Depends, Query, status

from portal.application.facility.availability_service import AvailabilityService
from portal.application.facility.booking_service import BookingService
from portal.application.facility.commands import BookingRoomLineCommand, CancelBookingCommand, CreateBookingCommand, RoomAvailabilityQueryCommand
from portal.application.facility.mappers import (
    create_id_result_to_api,
    member_preview_quote_result_to_api,
    member_preview_quote_to_command,
    room_availability_list_to_api,
)
from portal.application.facility.pricing_service import PricingService
from portal.application.facility.results import BookingListItemResult
from portal.container import Container
from portal.routers.auth_router import AuthRouter
from portal.serializers.apis.v1.facility import (
    MemberBookingCancel,
    MemberBookingCreate,
    MemberBookingList,
    MemberBookingListItem,
    MemberPreviewQuoteRequest,
    MemberPreviewQuoteResponse,
    MemberRoomAvailabilityList,
)
from portal.serializers.mixins.model_mixins import UUIDBaseModel

router: AuthRouter = AuthRouter()


def _booking_list_item_to_api(item: BookingListItemResult) -> MemberBookingListItem:
    return MemberBookingListItem(
        id=item.id,
        facility_id=item.facility_id,
        facility_name=item.facility_name,
        booking_type=item.booking_type,
        start_at=item.start_at,
        end_at=item.end_at,
        status=item.status,
        quoted_amount=str(item.quoted_amount) if item.quoted_amount is not None else None,
        currency=item.currency,
    )


@router.get(path="/rooms/availability", status_code=status.HTTP_200_OK, response_model=MemberRoomAvailabilityList, response_model_by_alias=True)
@inject
async def get_rooms_availability(
    date: date = Query(..., description="Target date YYYY-MM-DD"),
    ministry_id: Optional[UUID] = Query(None),
    availability_service: AvailabilityService = Depends(Provide[Container.availability_service]),
):
    result = await availability_service.get_rooms_availability(RoomAvailabilityQueryCommand(target_date=date, ministry_id=ministry_id))
    return room_availability_list_to_api(result)


@router.post(path="/preview-quote", status_code=status.HTTP_200_OK, response_model=MemberPreviewQuoteResponse, response_model_by_alias=True)
@inject
async def preview_quote(model: MemberPreviewQuoteRequest, pricing_service: PricingService = Depends(Provide[Container.pricing_service])):
    result = await pricing_service.preview_quote(command=member_preview_quote_to_command(model))
    return member_preview_quote_result_to_api(result)


@router.get(path="/bookings/mine", status_code=status.HTTP_200_OK, response_model=MemberBookingList, response_model_by_alias=True)
@inject
async def get_my_bookings(booking_service: BookingService = Depends(Provide[Container.booking_service])):
    items = await booking_service.list_my_bookings()
    return MemberBookingList(items=[_booking_list_item_to_api(item) for item in items])


@router.post(path="/bookings", status_code=status.HTTP_201_CREATED, response_model=UUIDBaseModel)
@inject
async def create_booking(model: MemberBookingCreate, booking_service: BookingService = Depends(Provide[Container.booking_service])):
    result = await booking_service.create_booking(
        CreateBookingCommand(
            start_at=model.start_at,
            end_at=model.end_at,
            is_mission_aligned=model.is_mission_aligned,
            ministry_id=model.ministry_id,
            rooms=[
                BookingRoomLineCommand(facility_id=line.facility_id, start_at=line.start_at, end_at=line.end_at, sequence=line.sequence) for line in model.rooms
            ],
            surcharge_codes=model.surcharge_codes,
            remark=model.remark,
        )
    )
    return create_id_result_to_api(result)


@router.post(path="/bookings/{booking_id}/cancel", status_code=status.HTTP_204_NO_CONTENT)
@inject
async def cancel_my_booking(booking_id: UUID, model: MemberBookingCancel, booking_service: BookingService = Depends(Provide[Container.booking_service])):
    await booking_service.cancel_my_booking(booking_id, CancelBookingCommand(scope=model.scope, cancel_reason=model.cancel_reason))
