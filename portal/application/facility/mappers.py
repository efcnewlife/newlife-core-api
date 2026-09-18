"""
Map between facility API serializers and application commands/results.
"""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from portal.application.content.mappers import file_grid_item_to_api
from portal.application.facility.commands import (
    BookingDraftLineCommand,
    BulkIdsCommand,
    CreateBookingDraftCommand,
    CreateDiscountRuleCommand,
    CreateRentalRateCommand,
    CreateRentalRateTemplateCommand,
    CreateRoomBlackoutCommand,
    CreateRoomCommand,
    CreateRoomSlotTemplateCommand,
    CreateSurchargeCommand,
    DeleteCommand,
    FacilityTranslationCommand,
    MemberBrowseQueryCommand,
    MemberPreviewQuoteCommand,
    MemberPreviewQuoteLineCommand,
    PagesQueryCommand,
    PreviewQuoteCommand,
    PreviewQuoteRoomLineCommand,
    UpdateBookingDraftCommand,
    UpdateDiscountRuleCommand,
    UpdateRentalRateCommand,
    UpdateRentalRateTemplateCommand,
    UpdateRoomBlackoutCommand,
    UpdateRoomCommand,
    UpdateRoomSlotTemplateCommand,
    UpdateSurchargeCommand,
)
from portal.application.facility.results import (
    BlackoutImpactResult,
    BookingDetailResult,
    BookingDraftResult,
    CreateIdResult,
    DayAvailabilityResult,
    DiscountRuleListResult,
    DiscountRuleResult,
    MemberBrowseBookingResult,
    MemberBrowseCardResult,
    MemberBrowsePageResult,
    ParticipantBookingDetailResult,
    ParticipantSeriesDetailResult,
    PreviewQuoteResult,
    RentalRateListResult,
    RentalRatePageResult,
    RentalRateResult,
    RentalRateTemplateListResult,
    RentalRateTemplatePageResult,
    RentalRateTemplateResult,
    RoomAvailabilityListResult,
    RoomAvailabilityResult,
    RoomBlackoutListResult,
    RoomBlackoutPageResult,
    RoomBlackoutResult,
    RoomDetailResult,
    RoomListResult,
    RoomPageResult,
    RoomSlotTemplateListResult,
    RoomSlotTemplatePageResult,
    RoomSlotTemplateResult,
    SurchargeListResult,
    SurchargeResult,
    TimeSlotResult,
    TranslationItemResult,
)
from portal.domain.common.mixins import UUIDBaseModel
from portal.domain.facility.constants import BookingType
from portal.serializers.admin.v1.facility.rental_catalog import (
    AdminDiscountRuleCreate,
    AdminDiscountRuleItem,
    AdminDiscountRuleList,
    AdminDiscountRuleUpdate,
    AdminSurchargeCreate,
    AdminSurchargeItem,
    AdminSurchargeList,
    AdminSurchargeUpdate,
)
from portal.serializers.admin.v1.facility.rental_rate import (
    AdminPreviewQuoteRequest,
    AdminPreviewQuoteResponse,
    AdminPreviewQuoteRoomLineResult,
    AdminRentalRateCreate,
    AdminRentalRateItem,
    AdminRentalRateList,
    AdminRentalRatePages,
    AdminRentalRateTemplateEmbed,
    AdminRentalRateUpdate,
)
from portal.serializers.admin.v1.facility.rental_rate_template import (
    AdminRentalRateTemplateCreate,
    AdminRentalRateTemplateItem,
    AdminRentalRateTemplateList,
    AdminRentalRateTemplatePages,
    AdminRentalRateTemplateUpdate,
)
from portal.serializers.admin.v1.facility.room import AdminRoomBulkAction, AdminRoomCreate, AdminRoomDetail, AdminRoomList, AdminRoomPages, AdminRoomUpdate
from portal.serializers.admin.v1.facility.room_blackout import (
    AdminBlackoutImpact,
    AdminRoomBlackoutCreate,
    AdminRoomBlackoutItem,
    AdminRoomBlackoutList,
    AdminRoomBlackoutPages,
    AdminRoomBlackoutUpdate,
)
from portal.serializers.admin.v1.facility.room_slot_template import (
    AdminRoomSlotTemplateCreate,
    AdminRoomSlotTemplateItem,
    AdminRoomSlotTemplateList,
    AdminRoomSlotTemplatePages,
    AdminRoomSlotTemplateUpdate,
)
from portal.serializers.admin.v1.facility.translation import AdminFacilityTranslationInput, AdminFacilityTranslationItem
from portal.serializers.apis.v1.facility import (
    MemberBookingActions,
    MemberBookingBrowseCard,
    MemberBookingBrowsePage,
    MemberBookingBrowseQuery,
    MemberBookingDetail,
    MemberBookingDetailRoom,
    MemberBookingDraftCreate,
    MemberBookingDraftDetail,
    MemberBookingDraftLine,
    MemberBookingDraftUpdate,
    MemberBookingListItem,
    MemberBookingTimelineEvent,
    MemberDayAvailability,
    MemberPreviewQuoteLineInput,
    MemberPreviewQuoteRequest,
    MemberPreviewQuoteResponse,
    MemberPreviewQuoteRoomLineResult,
    MemberRoomAvailabilityItem,
    MemberRoomAvailabilityList,
    MemberTimeSlot,
)
from portal.serializers.mixins import DeleteBaseModel, GenericQueryBaseModel


def pages_query_to_command(model: GenericQueryBaseModel) -> PagesQueryCommand:
    return PagesQueryCommand(
        page=model.page, page_size=model.page_size, order_by=model.order_by, descending=model.descending, deleted=model.deleted, keyword=model.keyword
    )


def delete_model_to_command(model: DeleteBaseModel) -> DeleteCommand:
    return DeleteCommand(reason=model.reason, permanent=model.permanent)


def bulk_action_to_command(model: AdminRoomBulkAction) -> BulkIdsCommand:
    return BulkIdsCommand(ids=model.ids)


def _translation_commands(translations: list[AdminFacilityTranslationInput] | None) -> list[FacilityTranslationCommand] | None:
    if translations is None:
        return None
    return [FacilityTranslationCommand(locale_id=item.locale_id, name=item.name, description=item.description, remark=item.remark) for item in translations]


def _translation_items_to_api(items: list[TranslationItemResult]) -> list[AdminFacilityTranslationItem]:
    return [AdminFacilityTranslationItem(locale_id=item.locale_id, name=item.name, description=item.description, remark=item.remark) for item in items]


def create_id_result_to_api(result: CreateIdResult) -> UUIDBaseModel:
    return UUIDBaseModel(id=result.id)


def create_room_to_command(model: AdminRoomCreate) -> CreateRoomCommand:
    return CreateRoomCommand(
        code=model.code,
        name=model.name,
        room_number=model.room_number,
        capacity=model.capacity,
        is_active=model.is_active,
        sequence=model.sequence,
        translations=_translation_commands(model.translations),
        file_ids=model.file_ids,
    )


def update_room_to_command(model: AdminRoomUpdate) -> UpdateRoomCommand:
    return UpdateRoomCommand(
        name=model.name,
        room_number=model.room_number,
        capacity=model.capacity,
        is_active=model.is_active,
        sequence=model.sequence,
        translations=_translation_commands(model.translations),
        file_ids=model.file_ids,
    )


def room_detail_to_api(result: RoomDetailResult) -> AdminRoomDetail:
    return AdminRoomDetail(
        id=result.id,
        code=result.code,
        name=result.name,
        room_number=result.room_number,
        capacity=result.capacity,
        is_active=result.is_active,
        sequence=result.sequence,
        created_at=result.created_at,
        created_by=result.created_by,
        updated_at=result.updated_at,
        updated_by=result.updated_by,
        delete_reason=result.delete_reason,
        description=result.description,
        translations=_translation_items_to_api(result.translations),
        files=[file_grid_item_to_api(item) for item in result.files],
    )


def room_page_result_to_api(result: RoomPageResult) -> AdminRoomPages:
    return AdminRoomPages(page=result.page, page_size=result.page_size, total=result.total, items=[room_detail_to_api(item) for item in result.items])


def room_list_result_to_api(result: RoomListResult) -> AdminRoomList:
    from portal.serializers.admin.v1.facility.room import AdminRoomBase

    return AdminRoomList(items=[AdminRoomBase(id=item.id, code=item.code, name=item.name) for item in result.items])


def create_room_slot_template_to_command(model: AdminRoomSlotTemplateCreate) -> CreateRoomSlotTemplateCommand:
    return CreateRoomSlotTemplateCommand.model_validate(model.model_dump())


def update_room_slot_template_to_command(model: AdminRoomSlotTemplateUpdate) -> UpdateRoomSlotTemplateCommand:
    return UpdateRoomSlotTemplateCommand.model_validate(model.model_dump())


def room_slot_template_to_api(result: RoomSlotTemplateResult) -> AdminRoomSlotTemplateItem:
    from portal.domain.facility.days_of_week_mask import mask_to_days

    payload = result.model_dump()
    payload["days_of_week"] = mask_to_days(result.days_of_week_mask)
    del payload["days_of_week_mask"]
    return AdminRoomSlotTemplateItem.model_validate(payload)


def room_slot_template_page_to_api(result: RoomSlotTemplatePageResult) -> AdminRoomSlotTemplatePages:
    return AdminRoomSlotTemplatePages(
        page=result.page, page_size=result.page_size, total=result.total, items=[room_slot_template_to_api(item) for item in result.items]
    )


def room_slot_template_list_to_api(result: RoomSlotTemplateListResult) -> AdminRoomSlotTemplateList:
    return AdminRoomSlotTemplateList(items=[room_slot_template_to_api(item) for item in result.items])


def room_slot_template_pages_query_to_command(model) -> tuple[PagesQueryCommand, UUID | None]:
    from portal.serializers.admin.v1.facility.room_slot_template import AdminRoomSlotTemplateQuery

    base = pages_query_to_command(model)
    if not isinstance(model, AdminRoomSlotTemplateQuery):
        return base, None
    return base, model.facility_id


def create_room_blackout_to_command(model: AdminRoomBlackoutCreate) -> CreateRoomBlackoutCommand:
    return CreateRoomBlackoutCommand.model_validate(model.model_dump())


def update_room_blackout_to_command(model: AdminRoomBlackoutUpdate) -> UpdateRoomBlackoutCommand:
    return UpdateRoomBlackoutCommand.model_validate(model.model_dump())


def room_blackout_to_api(result: RoomBlackoutResult) -> AdminRoomBlackoutItem:
    from portal.domain.facility.days_of_week_mask import mask_to_days

    payload = result.model_dump()
    if result.days_of_week_mask is not None:
        payload["days_of_week"] = mask_to_days(result.days_of_week_mask)
    else:
        payload["days_of_week"] = None
    del payload["days_of_week_mask"]
    return AdminRoomBlackoutItem.model_validate(payload)


def room_blackout_page_to_api(result: RoomBlackoutPageResult) -> AdminRoomBlackoutPages:
    return AdminRoomBlackoutPages(page=result.page, page_size=result.page_size, total=result.total, items=[room_blackout_to_api(item) for item in result.items])


def room_blackout_list_to_api(result: RoomBlackoutListResult) -> AdminRoomBlackoutList:
    return AdminRoomBlackoutList(items=[room_blackout_to_api(item) for item in result.items])


def blackout_impact_to_api(result: BlackoutImpactResult) -> AdminBlackoutImpact:
    return AdminBlackoutImpact.model_validate(result.model_dump())


def room_blackout_pages_query_to_command(model) -> tuple[PagesQueryCommand, UUID | None]:
    from portal.serializers.admin.v1.facility.room_blackout import AdminRoomBlackoutQuery

    base = pages_query_to_command(model)
    if not isinstance(model, AdminRoomBlackoutQuery):
        return base, None
    return base, model.facility_id


def create_rental_rate_template_to_command(model: AdminRentalRateTemplateCreate) -> CreateRentalRateTemplateCommand:
    return CreateRentalRateTemplateCommand(
        name=model.name,
        billing_unit=model.billing_unit,
        applicability=model.applicability,
        unit_amount=model.unit_amount,
        currency=model.currency,
        is_default=model.is_default,
        is_active=model.is_active,
    )


def update_rental_rate_template_to_command(model: AdminRentalRateTemplateUpdate) -> UpdateRentalRateTemplateCommand:
    return UpdateRentalRateTemplateCommand(
        name=model.name,
        billing_unit=model.billing_unit,
        applicability=model.applicability,
        unit_amount=model.unit_amount,
        currency=model.currency,
        is_default=model.is_default,
        is_active=model.is_active,
    )


def rental_rate_template_to_api(result: RentalRateTemplateResult) -> AdminRentalRateTemplateItem:
    return AdminRentalRateTemplateItem(
        id=result.id,
        name=result.name,
        billing_unit=result.billing_unit,
        applicability=result.applicability,
        unit_amount=result.unit_amount,
        currency=result.currency,
        is_default=result.is_default,
        is_active=result.is_active,
        created_at=result.created_at,
        created_by=result.created_by,
        updated_at=result.updated_at,
        updated_by=result.updated_by,
        delete_reason=result.delete_reason,
    )


def rental_rate_template_page_to_api(result: RentalRateTemplatePageResult) -> AdminRentalRateTemplatePages:
    return AdminRentalRateTemplatePages(
        page=result.page, page_size=result.page_size, total=result.total, items=[rental_rate_template_to_api(item) for item in result.items]
    )


def rental_rate_template_list_to_api(result: RentalRateTemplateListResult) -> AdminRentalRateTemplateList:
    return AdminRentalRateTemplateList(items=[rental_rate_template_to_api(item) for item in result.items])


def create_rental_rate_to_command(model: AdminRentalRateCreate) -> CreateRentalRateCommand:
    return CreateRentalRateCommand(facility_id=model.facility_id, template_id=model.template_id, is_active=model.is_active)


def update_rental_rate_to_command(model: AdminRentalRateUpdate) -> UpdateRentalRateCommand:
    return UpdateRentalRateCommand(facility_id=model.facility_id, template_id=model.template_id, is_active=model.is_active)


def rental_rate_to_api(result: RentalRateResult) -> AdminRentalRateItem:
    template_embed = None
    if result.template_id and result.billing_unit is not None:
        template_embed = AdminRentalRateTemplateEmbed(
            id=result.template_id,
            name=result.template_name or "",
            billing_unit=result.billing_unit,
            applicability=result.applicability,
            unit_amount=result.unit_amount,
            currency=result.currency,
            is_default=result.is_default,
            is_active=result.template_is_active,
        )
    return AdminRentalRateItem(
        id=result.id,
        facility_id=result.facility_id,
        template_id=result.template_id,
        is_active=result.is_active,
        created_at=result.created_at,
        created_by=result.created_by,
        updated_at=result.updated_at,
        updated_by=result.updated_by,
        delete_reason=result.delete_reason,
        template=template_embed,
    )


def rental_rate_page_to_api(result: RentalRatePageResult) -> AdminRentalRatePages:
    return AdminRentalRatePages(page=result.page, page_size=result.page_size, total=result.total, items=[rental_rate_to_api(item) for item in result.items])


def rental_rate_list_to_api(result: RentalRateListResult) -> AdminRentalRateList:
    return AdminRentalRateList(items=[rental_rate_to_api(item) for item in result.items])


def rental_rate_pages_query_to_command(model) -> tuple[PagesQueryCommand, UUID | None]:
    from portal.serializers.admin.v1.facility.rental_rate import AdminRentalRateQuery

    base = pages_query_to_command(model)
    if not isinstance(model, AdminRentalRateQuery):
        return base, None
    return base, model.facility_id


def preview_quote_to_command(model: AdminPreviewQuoteRequest) -> PreviewQuoteCommand:
    return PreviewQuoteCommand(
        booking_type=BookingType(model.booking_type),
        is_mission_aligned=model.is_mission_aligned,
        currency=model.currency,
        as_of_date=model.as_of_date,
        room_lines=[PreviewQuoteRoomLineCommand(facility_id=line.facility_id, billed_hours=line.billed_hours) for line in model.room_lines],
        surcharge_codes=model.surcharge_codes,
    )


def preview_quote_result_to_api(result: PreviewQuoteResult) -> AdminPreviewQuoteResponse:
    return AdminPreviewQuoteResponse(
        subtotal_amount=result.subtotal_amount,
        discount_percent=result.discount_percent,
        discount_amount=result.discount_amount,
        surcharge_amount=result.surcharge_amount,
        quoted_amount=result.quoted_amount,
        currency=result.currency,
        room_lines=[
            AdminPreviewQuoteRoomLineResult(
                facility_id=line.facility_id,
                billed_hours=line.billed_hours,
                rental_rate_name=line.rental_rate_name,
                billing_unit=line.billing_unit,
                unit_amount=line.unit_amount,
                currency=line.currency,
                applicability=line.applicability,
                is_default=line.is_default,
                line_subtotal=line.line_subtotal,
            )
            for line in result.room_lines
        ],
    )


def member_preview_quote_to_command(model: MemberPreviewQuoteRequest) -> MemberPreviewQuoteCommand:
    return MemberPreviewQuoteCommand(
        is_mission_aligned=model.is_mission_aligned,
        ministry_id=model.ministry_id,
        currency=model.currency,
        surcharge_codes=model.surcharge_codes,
        lines=[MemberPreviewQuoteLineCommand(facility_id=line.facility_id, start_at=line.start_at, end_at=line.end_at) for line in model.lines],
    )


def member_preview_quote_result_to_api(result: PreviewQuoteResult) -> MemberPreviewQuoteResponse:
    return MemberPreviewQuoteResponse(
        subtotal_amount=result.subtotal_amount,
        discount_percent=result.discount_percent,
        discount_amount=result.discount_amount,
        surcharge_amount=result.surcharge_amount,
        quoted_amount=result.quoted_amount,
        currency=result.currency,
        room_lines=[
            MemberPreviewQuoteRoomLineResult(
                facility_id=line.facility_id,
                billed_hours=line.billed_hours,
                rental_rate_name=line.rental_rate_name,
                billing_unit=line.billing_unit,
                unit_amount=line.unit_amount,
                currency=line.currency,
                applicability=line.applicability,
                is_default=line.is_default,
                line_subtotal=line.line_subtotal,
            )
            for line in result.room_lines
        ],
    )


def room_availability_item_to_api(item: RoomAvailabilityResult) -> MemberRoomAvailabilityItem:
    def slot_to_api(slot: TimeSlotResult) -> MemberTimeSlot:
        return MemberTimeSlot(start=slot.start, end=slot.end)

    def day_to_api(day: DayAvailabilityResult) -> MemberDayAvailability:
        return MemberDayAvailability(am=[slot_to_api(s) for s in day.am], pm=[slot_to_api(s) for s in day.pm])

    return MemberRoomAvailabilityItem(
        id=item.id,
        code=item.code,
        name=item.name,
        room_number=item.room_number,
        capacity=item.capacity,
        is_active=item.is_active,
        photo_urls=item.photo_urls,
        availability=day_to_api(item.availability),
    )


def room_availability_list_to_api(result: RoomAvailabilityListResult) -> MemberRoomAvailabilityList:
    return MemberRoomAvailabilityList(
        date=result.date, items=[room_availability_item_to_api(item) for item in result.items], max_booking_lines=result.max_booking_lines
    )


def member_booking_detail_to_api(result: ParticipantBookingDetailResult) -> MemberBookingDetail:
    return MemberBookingDetail(
        id=result.id,
        title=result.title,
        status=result.status,
        booking_type=result.booking_type,
        series_id=result.series_id,
        start_at=result.start_at,
        end_at=result.end_at,
        ministry_id=result.ministry_id,
        ministry_name=result.ministry_name,
        remark=result.remark,
        booker_display_name=result.booker_display_name,
        booker_email=result.booker_email,
        quoted_amount=result.quoted_amount,
        subtotal_amount=result.subtotal_amount,
        discount_percent=result.discount_percent,
        discount_amount=result.discount_amount,
        surcharge_amount=result.surcharge_amount,
        currency=result.currency,
        payment_hold_expires_at=result.payment_hold_expires_at,
        is_booker=result.is_booker,
        is_view_only=result.is_view_only,
        rooms=[
            MemberBookingDetailRoom(
                id=line.id,
                facility_id=line.facility_id,
                facility_name=line.facility_name,
                sequence=line.sequence,
                start_at=line.start_at,
                end_at=line.end_at,
                billed_hours=line.billed_hours,
                rental_rate_name=line.rental_rate_name,
                billing_unit=line.billing_unit,
                unit_amount=line.unit_amount,
                currency=line.currency,
                line_subtotal=line.line_subtotal,
                photo_urls=line.photo_urls,
            )
            for line in result.rooms
        ],
        timeline=[MemberBookingTimelineEvent(kind=event.kind, occurred_at=event.occurred_at, reason=event.reason) for event in result.timeline],
        actions=MemberBookingActions(
            can_edit_title=result.actions.can_edit_title,
            can_cancel=result.actions.can_cancel,
            can_view_payment_instructions=result.actions.can_view_payment_instructions,
            can_book_again=result.actions.can_book_again,
            book_again_date=result.actions.book_again_date,
        ),
    )


def member_browse_query_to_command(model: MemberBookingBrowseQuery) -> MemberBrowseQueryCommand:
    return MemberBrowseQueryCommand(section=model.section, page=model.page, page_size=model.page_size)


def member_browse_booking_to_api(item: MemberBrowseBookingResult) -> MemberBookingListItem:
    return MemberBookingListItem(
        id=item.id,
        title=item.title,
        facility_id=item.facility_id,
        facility_name=item.facility_name,
        booking_type=item.booking_type,
        series_id=item.series_id,
        start_at=item.start_at,
        end_at=item.end_at,
        status=item.status,
        quoted_amount=str(item.quoted_amount) if item.quoted_amount is not None else None,
        currency=item.currency,
    )


def member_browse_card_to_api(card: MemberBrowseCardResult) -> MemberBookingBrowseCard:
    return MemberBookingBrowseCard(
        kind=card.kind,
        is_booker=card.is_booker,
        is_view_only=card.is_view_only,
        photo_urls=card.photo_urls,
        booking=member_browse_booking_to_api(card.booking) if card.booking else None,
        series_id=card.series_id,
        series_title=card.series_title,
        occurrences=[member_browse_booking_to_api(item) for item in card.occurrences],
    )


def member_browse_page_to_api(result: MemberBrowsePageResult) -> MemberBookingBrowsePage:
    return MemberBookingBrowsePage(
        page=result.page,
        page_size=result.page_size,
        total=result.total,
        section=result.section,
        items=[member_browse_card_to_api(item) for item in result.items],
    )


def member_booking_draft_create_to_command(model: MemberBookingDraftCreate) -> CreateBookingDraftCommand:
    return CreateBookingDraftCommand(
        ministry_id=model.ministry_id,
        lines=[
            BookingDraftLineCommand(facility_id=line.facility_id, start_at=line.start_at, end_at=line.end_at, sequence=line.sequence) for line in model.lines
        ],
    )


def member_booking_draft_update_to_command(model: MemberBookingDraftUpdate) -> UpdateBookingDraftCommand:
    return UpdateBookingDraftCommand(
        ministry_id=model.ministry_id,
        lines=[
            BookingDraftLineCommand(facility_id=line.facility_id, start_at=line.start_at, end_at=line.end_at, sequence=line.sequence) for line in model.lines
        ],
    )


def booking_draft_result_to_api(result: BookingDraftResult) -> MemberBookingDraftDetail:
    return MemberBookingDraftDetail(
        id=result.id,
        date=result.date,
        ministry_id=result.ministry_id,
        lines=[
            MemberBookingDraftLine(
                facility_id=line.facility_id, start_at=line.start_at, end_at=line.end_at, sequence=line.sequence, is_available=line.is_available
            )
            for line in result.lines
        ],
        subtotal_amount=result.subtotal_amount,
        discount_percent=result.discount_percent,
        discount_amount=result.discount_amount,
        surcharge_amount=result.surcharge_amount,
        quoted_amount=result.quoted_amount,
        currency=result.currency,
    )


def create_discount_rule_to_command(model: AdminDiscountRuleCreate) -> CreateDiscountRuleCommand:
    return CreateDiscountRuleCommand.model_validate(model.model_dump())


def update_discount_rule_to_command(model: AdminDiscountRuleUpdate) -> UpdateDiscountRuleCommand:
    return UpdateDiscountRuleCommand.model_validate(model.model_dump())


def discount_rule_to_api(result: DiscountRuleResult) -> AdminDiscountRuleItem:
    return AdminDiscountRuleItem.model_validate(result.model_dump())


def discount_rule_list_to_api(result: DiscountRuleListResult) -> AdminDiscountRuleList:
    return AdminDiscountRuleList(items=[discount_rule_to_api(item) for item in result.items])


def create_surcharge_to_command(model: AdminSurchargeCreate) -> CreateSurchargeCommand:
    return CreateSurchargeCommand.model_validate(model.model_dump())


def update_surcharge_to_command(model: AdminSurchargeUpdate) -> UpdateSurchargeCommand:
    return UpdateSurchargeCommand.model_validate(model.model_dump())


def surcharge_to_api(result: SurchargeResult) -> AdminSurchargeItem:
    return AdminSurchargeItem.model_validate(result.model_dump())


def surcharge_list_to_api(result: SurchargeListResult) -> AdminSurchargeList:
    return AdminSurchargeList(items=[surcharge_to_api(item) for item in result.items])


def booking_pages_query_to_command(model) -> "BookingPagesQueryCommand":
    from portal.application.facility.commands import BookingPagesQueryCommand
    from portal.serializers.admin.v1.facility.booking import AdminBookingQuery

    base = pages_query_to_command(model)
    if not isinstance(model, AdminBookingQuery):
        return BookingPagesQueryCommand(**base.model_dump())
    return BookingPagesQueryCommand(
        **base.model_dump(),
        facility_id=model.facility_id,
        user_id=model.user_id,
        status=model.status,
        booking_type=model.booking_type,
        date_from=model.date_from,
        date_to=model.date_to,
    )


def booking_range_query_to_command(model) -> "BookingRangeQueryCommand":
    from portal.application.facility.commands import BookingRangeQueryCommand
    from portal.serializers.admin.v1.facility.booking import AdminBookingRangeQuery

    if not isinstance(model, AdminBookingRangeQuery):
        raise TypeError("Expected AdminBookingRangeQuery")
    return BookingRangeQueryCommand(date_from=model.date_from, date_to=model.date_to, include_cancelled=model.include_cancelled)


def override_log_pages_query_to_command(model) -> "OverrideLogPagesQueryCommand":
    from portal.application.facility.commands import OverrideLogPagesQueryCommand
    from portal.serializers.admin.v1.facility.override_log import AdminOverrideLogQuery

    base = pages_query_to_command(model)
    if not isinstance(model, AdminOverrideLogQuery):
        return OverrideLogPagesQueryCommand(**base.model_dump())
    return OverrideLogPagesQueryCommand(
        **base.model_dump(), facility_id=model.facility_id, overridden_by_id=model.overridden_by_id, date_from=model.date_from, date_to=model.date_to
    )


def create_booking_to_command(model) -> "CreateBookingCommand":
    from portal.application.facility.commands import BookingRoomLineCommand, CreateBookingCommand
    from portal.serializers.admin.v1.facility.booking import AdminBookingCreate

    if not isinstance(model, AdminBookingCreate):
        raise TypeError("Expected AdminBookingCreate")
    return CreateBookingCommand(
        user_id=model.user_id,
        title=model.title,
        start_at=model.start_at,
        end_at=model.end_at,
        is_mission_aligned=model.is_mission_aligned,
        ministry_id=model.ministry_id,
        rooms=[
            BookingRoomLineCommand(facility_id=room.facility_id, start_at=room.start_at, end_at=room.end_at, sequence=room.sequence) for room in model.rooms
        ],
        surcharge_codes=model.surcharge_codes,
        remark=model.remark,
    )


def update_booking_to_command(model) -> "UpdateBookingCommand":
    from portal.application.facility.commands import BookingRoomLineCommand, UpdateBookingCommand
    from portal.serializers.admin.v1.facility.booking import AdminBookingUpdate

    return UpdateBookingCommand(
        start_at=model.start_at,
        end_at=model.end_at,
        is_mission_aligned=model.is_mission_aligned,
        ministry_id=model.ministry_id,
        rooms=[
            BookingRoomLineCommand(facility_id=room.facility_id, start_at=room.start_at, end_at=room.end_at, sequence=room.sequence) for room in model.rooms
        ],
        surcharge_codes=model.surcharge_codes,
    )


def cancel_booking_to_command(model) -> "CancelBookingCommand":
    from portal.application.facility.commands import CancelBookingCommand

    return CancelBookingCommand(scope=model.scope, cancel_reason=model.cancel_reason)


def booking_page_to_api(result) -> "AdminBookingPages":
    from portal.serializers.admin.v1.facility.booking import AdminBookingDetail, AdminBookingPages

    return AdminBookingPages(
        page=result.page, page_size=result.page_size, total=result.total, items=[AdminBookingDetail.model_validate(item.model_dump()) for item in result.items]
    )


def booking_range_to_api(result) -> "AdminBookingRange":
    from portal.serializers.admin.v1.facility.booking import AdminBookingListItem, AdminBookingRange

    return AdminBookingRange(items=[AdminBookingListItem.model_validate(item.model_dump()) for item in result.items])


def booking_detail_to_api(result) -> "AdminBookingDetail":
    from portal.serializers.admin.v1.facility.booking import AdminBookingDetail

    return AdminBookingDetail.model_validate(result.model_dump())


def override_log_page_to_api(result) -> "AdminOverrideLogPages":
    from portal.serializers.admin.v1.facility.override_log import AdminOverrideLogPages

    return AdminOverrideLogPages(page=result.page, page_size=result.page_size, total=result.total, items=[item for item in result.items])


def create_recurring_booking_series_to_command(model) -> "CreateRecurringBookingSeriesCommand":
    from portal.application.facility.commands import BookingRoomLineCommand, CreateRecurringBookingSeriesCommand

    return CreateRecurringBookingSeriesCommand(
        user_id=getattr(model, "user_id", None),
        title=getattr(model, "title", None),
        ministry_id=model.ministry_id,
        first_occurrence_date=model.first_occurrence_date,
        last_occurrence_date=model.last_occurrence_date,
        local_start_time=model.local_start_time,
        local_end_time=model.local_end_time,
        is_mission_aligned=model.is_mission_aligned,
        rooms=[BookingRoomLineCommand(facility_id=room.facility_id, sequence=room.sequence) for room in model.rooms],
        surcharge_codes=model.surcharge_codes,
        remark=model.remark,
        excluded_dates=list(getattr(model, "excluded_dates", []) or []),
    )


def recurring_booking_series_to_admin_api(result) -> "AdminRecurringBookingSeriesDetail":
    from portal.serializers.admin.v1.facility.booking_series import AdminRecurringBookingSeriesDetail

    return AdminRecurringBookingSeriesDetail.model_validate(result.model_dump())


def recurring_booking_series_to_member_api(result) -> "MemberRecurringBookingSeriesDetail":
    from portal.serializers.apis.v1.facility import MemberRecurringBookingSeriesDetail

    return MemberRecurringBookingSeriesDetail(
        id=result.id,
        title=result.title,
        ministry_id=result.ministry_id,
        ministry_name=getattr(result, "ministry_name", None),
        remark=getattr(result, "remark", None),
        first_occurrence_date=result.first_occurrence_date,
        last_occurrence_date=result.last_occurrence_date,
        local_start_time=result.local_start_time,
        local_end_time=result.local_end_time,
        status=result.status,
        payment_hold_expires_at=result.payment_hold_expires_at,
        quoted_amount=result.quoted_amount,
        currency=result.currency,
        occurrence_count=result.occurrence_count,
        is_priority=getattr(result, "is_priority", False),
        user_id=getattr(result, "user_id", None),
        booker_display_name=getattr(result, "booker_display_name", None) or getattr(result, "user_display_name", None),
        booker_email=getattr(result, "booker_email", None) or getattr(result, "user_email", None),
        is_booker=getattr(result, "is_booker", True),
        is_view_only=getattr(result, "is_view_only", False),
        timeline=[MemberBookingTimelineEvent(kind=event.kind, occurred_at=event.occurred_at, reason=event.reason) for event in getattr(result, "timeline", [])],
        actions=_member_actions_to_api(getattr(result, "actions", None)),
        occurrences=[_member_occurrence_to_api(item) for item in result.occurrences],
    )


def participant_series_detail_to_api(result: ParticipantSeriesDetailResult) -> "MemberRecurringBookingSeriesDetail":
    return recurring_booking_series_to_member_api(result)


def _member_actions_to_api(actions) -> MemberBookingActions:
    if actions is None:
        return MemberBookingActions(can_edit_title=False, can_cancel=False, can_view_payment_instructions=False, can_book_again=False)
    return MemberBookingActions(
        can_edit_title=actions.can_edit_title,
        can_cancel=actions.can_cancel,
        can_view_payment_instructions=actions.can_view_payment_instructions,
        can_book_again=actions.can_book_again,
        book_again_date=actions.book_again_date,
    )


def _member_occurrence_to_api(item) -> MemberBookingDetail:
    if isinstance(item, ParticipantBookingDetailResult):
        return member_booking_detail_to_api(item)
    return MemberBookingDetail(
        id=item.id,
        title=getattr(item, "title", ""),
        status=item.status,
        booking_type=getattr(item, "booking_type", ""),
        start_at=item.start_at,
        end_at=item.end_at,
        quoted_amount=item.quoted_amount,
        currency=item.currency,
    )


def recurring_booking_preview_to_admin_api(result) -> "AdminRecurringBookingPreview":
    from portal.serializers.admin.v1.facility.booking_series import AdminRecurringBookingPreview

    return AdminRecurringBookingPreview.model_validate(result.model_dump())


def recurring_booking_preview_to_member_api(result) -> "MemberRecurringBookingPreview":
    from portal.serializers.apis.v1.facility import MemberRecurringBookingPreview

    return MemberRecurringBookingPreview.model_validate(result.model_dump())


def recurring_booking_window_status_to_api(result) -> "MemberRecurringBookingWindowStatus":
    from portal.serializers.apis.v1.facility import MemberRecurringBookingWindowStatus

    return MemberRecurringBookingWindowStatus.model_validate(result.model_dump())


def pending_payment_series_list_to_admin_api(result) -> "AdminPendingPaymentSeriesList":
    from portal.serializers.admin.v1.facility.booking_series import AdminPendingPaymentSeriesList

    return AdminPendingPaymentSeriesList.model_validate(result.model_dump())


def cancel_recurring_booking_series_to_command(model) -> "CancelRecurringBookingSeriesCommand":
    from portal.application.facility.commands import CancelRecurringBookingSeriesCommand

    return CancelRecurringBookingSeriesCommand(scope=model.scope, occurrence_id=model.occurrence_id, cancel_reason=model.cancel_reason)


def update_title_to_command(model) -> "UpdateTitleCommand":
    from portal.application.facility.commands import UpdateTitleCommand

    return UpdateTitleCommand(title=model.title)
