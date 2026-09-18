"""
Member facility API routes (availability + bookings).
"""

from datetime import date
from typing import Annotated, Optional
from uuid import UUID

from dependency_injector.wiring import Provide, inject
from fastapi import Depends, Query, status

from portal.application.facility.availability_service import AvailabilityService
from portal.application.facility.booking_draft_service import BookingDraftService
from portal.application.facility.booking_service import BookingService
from portal.application.facility.commands import BookingRoomLineCommand, CancelBookingCommand, CreateBookingCommand, RoomAvailabilityQueryCommand
from portal.application.facility.mappers import (
    booking_draft_result_to_api,
    cancel_recurring_booking_series_to_command,
    create_id_result_to_api,
    create_recurring_booking_series_to_command,
    member_booking_detail_to_api,
    member_booking_draft_create_to_command,
    member_booking_draft_update_to_command,
    member_browse_page_to_api,
    member_browse_query_to_command,
    member_preview_quote_result_to_api,
    member_preview_quote_to_command,
    member_recurring_series_draft_create_to_command,
    member_recurring_series_draft_update_to_command,
    participant_series_detail_to_api,
    recurring_booking_preview_to_member_api,
    recurring_booking_series_to_member_api,
    recurring_booking_window_status_to_api,
    recurring_series_draft_result_to_api,
    room_availability_list_to_api,
    update_title_to_command,
)
from portal.application.facility.recurring_booking_service import RecurringBookingService
from portal.application.facility.recurring_series_draft_service import RecurringSeriesDraftService
from portal.container import Container
from portal.routers.auth_router import AuthRouter
from portal.serializers.apis.v1.facility import (
    MemberBookingBrowsePage,
    MemberBookingBrowseQuery,
    MemberBookingCancel,
    MemberBookingCreate,
    MemberBookingDetail,
    MemberBookingDraftCreate,
    MemberBookingDraftDetail,
    MemberBookingDraftUpdate,
    MemberBookingTitleUpdate,
    MemberPreviewQuoteRequest,
    MemberPreviewQuoteResponse,
    MemberRecurringBookingPreview,
    MemberRecurringBookingSeriesCancel,
    MemberRecurringBookingSeriesCreate,
    MemberRecurringBookingSeriesDetail,
    MemberRecurringBookingSeriesProposal,
    MemberRecurringBookingSeriesTitleUpdate,
    MemberRecurringBookingWindowStatus,
    MemberRecurringSeriesDraftCreate,
    MemberRecurringSeriesDraftDetail,
    MemberRecurringSeriesDraftUpdate,
    MemberRoomAvailabilityList,
)
from portal.serializers.mixins.model_mixins import UUIDBaseModel

router: AuthRouter = AuthRouter()


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
async def preview_quote(model: MemberPreviewQuoteRequest, booking_service: BookingService = Depends(Provide[Container.booking_service])):
    result = await booking_service.preview_quote_for_member(member_preview_quote_to_command(model))
    return member_preview_quote_result_to_api(result)


@router.get(path="/bookings/mine", status_code=status.HTTP_200_OK, response_model=MemberBookingBrowsePage, response_model_by_alias=True)
@inject
async def get_my_bookings(
    query_model: Annotated[MemberBookingBrowseQuery, Query()], booking_service: BookingService = Depends(Provide[Container.booking_service])
):
    result = await booking_service.browse_my_bookings(member_browse_query_to_command(query_model))
    return member_browse_page_to_api(result)


@router.get(path="/bookings/{booking_id}", status_code=status.HTTP_200_OK, response_model=MemberBookingDetail, response_model_by_alias=True)
@inject
async def get_my_booking(booking_id: UUID, booking_service: BookingService = Depends(Provide[Container.booking_service])):
    result = await booking_service.get_my_booking_by_id(booking_id)
    return member_booking_detail_to_api(result)


@router.patch(path="/bookings/{booking_id}/title", status_code=status.HTTP_200_OK, response_model=MemberBookingDetail, response_model_by_alias=True)
@inject
async def update_my_booking_title(
    booking_id: UUID, model: MemberBookingTitleUpdate, booking_service: BookingService = Depends(Provide[Container.booking_service])
):
    result = await booking_service.update_my_booking_title(booking_id, update_title_to_command(model))
    return member_booking_detail_to_api(result)


@router.post(path="/booking-series/preview", status_code=status.HTTP_200_OK, response_model=MemberRecurringBookingPreview, response_model_by_alias=True)
@inject
async def preview_booking_series(
    model: MemberRecurringBookingSeriesProposal, recurring_booking_service: RecurringBookingService = Depends(Provide[Container.recurring_booking_service])
):
    result = await recurring_booking_service.preview_conflicts(create_recurring_booking_series_to_command(model))
    return recurring_booking_preview_to_member_api(result)


@router.get(
    path="/booking-series/availability-window", status_code=status.HTTP_200_OK, response_model=MemberRecurringBookingWindowStatus, response_model_by_alias=True
)
@inject
async def get_booking_series_availability_window(
    first_occurrence_date: Optional[date] = Query(None),
    recurring_booking_service: RecurringBookingService = Depends(Provide[Container.recurring_booking_service]),
):
    result = await recurring_booking_service.get_window_status(first_occurrence_date)
    return recurring_booking_window_status_to_api(result)


@router.post(path="/booking-series", status_code=status.HTTP_201_CREATED, response_model=MemberRecurringBookingSeriesDetail, response_model_by_alias=True)
@inject
async def create_booking_series(
    model: MemberRecurringBookingSeriesCreate, recurring_booking_service: RecurringBookingService = Depends(Provide[Container.recurring_booking_service])
):
    result = await recurring_booking_service.create_series(create_recurring_booking_series_to_command(model))
    return recurring_booking_series_to_member_api(result)


@router.get(path="/booking-series/{series_id}", status_code=status.HTTP_200_OK, response_model=MemberRecurringBookingSeriesDetail, response_model_by_alias=True)
@inject
async def get_my_booking_series(series_id: UUID, recurring_booking_service: RecurringBookingService = Depends(Provide[Container.recurring_booking_service])):
    result = await recurring_booking_service.get_my_series_detail(series_id)
    return participant_series_detail_to_api(result)


@router.patch(
    path="/booking-series/{series_id}/title", status_code=status.HTTP_200_OK, response_model=MemberRecurringBookingSeriesDetail, response_model_by_alias=True
)
@inject
async def update_my_booking_series_title(
    series_id: UUID,
    model: MemberRecurringBookingSeriesTitleUpdate,
    recurring_booking_service: RecurringBookingService = Depends(Provide[Container.recurring_booking_service]),
):
    result = await recurring_booking_service.update_my_series_title(series_id, update_title_to_command(model))
    return recurring_booking_series_to_member_api(result)


@router.post(
    path="/booking-series/{series_id}/cancel", status_code=status.HTTP_200_OK, response_model=MemberRecurringBookingSeriesDetail, response_model_by_alias=True
)
@inject
async def cancel_my_booking_series(
    series_id: UUID,
    model: MemberRecurringBookingSeriesCancel,
    recurring_booking_service: RecurringBookingService = Depends(Provide[Container.recurring_booking_service]),
):
    result = await recurring_booking_service.cancel_my_series(series_id, cancel_recurring_booking_series_to_command(model))
    return recurring_booking_series_to_member_api(result)


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
            booking_draft_id=model.booking_draft_id,
            title=model.title,
        )
    )
    return create_id_result_to_api(result)


@router.post(path="/bookings/{booking_id}/cancel", status_code=status.HTTP_204_NO_CONTENT)
@inject
async def cancel_my_booking(booking_id: UUID, model: MemberBookingCancel, booking_service: BookingService = Depends(Provide[Container.booking_service])):
    await booking_service.cancel_my_booking(booking_id, CancelBookingCommand(scope=model.scope, cancel_reason=model.cancel_reason))


@router.post(path="/booking-drafts", status_code=status.HTTP_201_CREATED, response_model=UUIDBaseModel)
@inject
async def create_booking_draft(model: MemberBookingDraftCreate, booking_draft_service: BookingDraftService = Depends(Provide[Container.booking_draft_service])):
    result = await booking_draft_service.create_draft(member_booking_draft_create_to_command(model))
    return create_id_result_to_api(result)


@router.delete(path="/booking-drafts", status_code=status.HTTP_204_NO_CONTENT)
@inject
async def delete_my_booking_drafts(booking_draft_service: BookingDraftService = Depends(Provide[Container.booking_draft_service])):
    await booking_draft_service.delete_all_my_drafts()


@router.get(path="/booking-drafts/{booking_draft_id}", status_code=status.HTTP_200_OK, response_model=MemberBookingDraftDetail, response_model_by_alias=True)
@inject
async def get_booking_draft(booking_draft_id: UUID, booking_draft_service: BookingDraftService = Depends(Provide[Container.booking_draft_service])):
    result = await booking_draft_service.get_draft(booking_draft_id)
    return booking_draft_result_to_api(result)


@router.patch(path="/booking-drafts/{booking_draft_id}", status_code=status.HTTP_200_OK, response_model=MemberBookingDraftDetail, response_model_by_alias=True)
@inject
async def update_booking_draft(
    booking_draft_id: UUID, model: MemberBookingDraftUpdate, booking_draft_service: BookingDraftService = Depends(Provide[Container.booking_draft_service])
):
    result = await booking_draft_service.update_draft(booking_draft_id, member_booking_draft_update_to_command(model))
    return booking_draft_result_to_api(result)


@router.post(path="/booking-series-drafts", status_code=status.HTTP_201_CREATED, response_model=UUIDBaseModel)
@inject
async def create_booking_series_draft(
    model: MemberRecurringSeriesDraftCreate,
    recurring_series_draft_service: RecurringSeriesDraftService = Depends(Provide[Container.recurring_series_draft_service]),
):
    result = await recurring_series_draft_service.create_draft(member_recurring_series_draft_create_to_command(model))
    return create_id_result_to_api(result)


@router.delete(path="/booking-series-drafts", status_code=status.HTTP_204_NO_CONTENT)
@inject
async def delete_my_booking_series_drafts(
    recurring_series_draft_service: RecurringSeriesDraftService = Depends(Provide[Container.recurring_series_draft_service]),
):
    await recurring_series_draft_service.delete_all_my_drafts()


@router.get(
    path="/booking-series-drafts/{series_draft_id}",
    status_code=status.HTTP_200_OK,
    response_model=MemberRecurringSeriesDraftDetail,
    response_model_by_alias=True,
)
@inject
async def get_booking_series_draft(
    series_draft_id: UUID, recurring_series_draft_service: RecurringSeriesDraftService = Depends(Provide[Container.recurring_series_draft_service])
):
    result = await recurring_series_draft_service.get_draft(series_draft_id)
    return recurring_series_draft_result_to_api(result)


@router.patch(
    path="/booking-series-drafts/{series_draft_id}",
    status_code=status.HTTP_200_OK,
    response_model=MemberRecurringSeriesDraftDetail,
    response_model_by_alias=True,
)
@inject
async def update_booking_series_draft(
    series_draft_id: UUID,
    model: MemberRecurringSeriesDraftUpdate,
    recurring_series_draft_service: RecurringSeriesDraftService = Depends(Provide[Container.recurring_series_draft_service]),
):
    result = await recurring_series_draft_service.update_draft(series_draft_id, member_recurring_series_draft_update_to_command(model))
    return recurring_series_draft_result_to_api(result)


@router.post(
    path="/booking-series-drafts/{series_draft_id}/confirm",
    status_code=status.HTTP_201_CREATED,
    response_model=MemberRecurringBookingSeriesDetail,
    response_model_by_alias=True,
)
@inject
async def confirm_booking_series_draft(
    series_draft_id: UUID, recurring_series_draft_service: RecurringSeriesDraftService = Depends(Provide[Container.recurring_series_draft_service])
):
    result = await recurring_series_draft_service.confirm_draft(series_draft_id)
    return recurring_booking_series_to_member_api(result)
