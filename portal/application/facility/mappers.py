"""
Map between facility API serializers and application commands/results.
"""
from uuid import UUID

from portal.application.facility.commands import (
    BulkIdsCommand,
    CreateDiscountRuleCommand,
    CreateRentalRateCommand,
    CreateRoomCommand,
    CreateRoomSlotTemplateCommand,
    CreateSurchargeCommand,
    DeleteCommand,
    FacilityTranslationCommand,
    PagesQueryCommand,
    PreviewQuoteCommand,
    PreviewQuoteRoomLineCommand,
    UpdateDiscountRuleCommand,
    UpdatePolicySettingCommand,
    UpdateRentalRateCommand,
    UpdateRoomCommand,
    UpdateRoomSlotTemplateCommand,
    UpdateSurchargeCommand,
)
from portal.application.facility.results import (
    CreateIdResult,
    DiscountRuleListResult,
    DiscountRuleResult,
    PolicySettingListResult,
    PolicySettingResult,
    PreviewQuoteResult,
    RentalRateListResult,
    RentalRatePageResult,
    RentalRateResult,
    RoomDetailResult,
    RoomListResult,
    RoomPageResult,
    RoomSlotTemplateListResult,
    RoomSlotTemplatePageResult,
    RoomSlotTemplateResult,
    SurchargeListResult,
    SurchargeResult,
    TranslationItemResult,
)
from portal.domain.facility.constants import BookingType
from portal.domain.common.mixins import UUIDBaseModel
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
from portal.serializers.admin.v1.facility.rental_rate import (
    AdminPreviewQuoteRequest,
    AdminPreviewQuoteResponse,
    AdminPreviewQuoteRoomLineResult,
    AdminRentalRateCreate,
    AdminRentalRateItem,
    AdminRentalRateList,
    AdminRentalRatePages,
    AdminRentalRateUpdate,
)
from portal.serializers.admin.v1.facility.room import (
    AdminRoomBulkAction,
    AdminRoomCreate,
    AdminRoomDetail,
    AdminRoomList,
    AdminRoomPages,
    AdminRoomUpdate,
)
from portal.serializers.admin.v1.facility.room_slot_template import (
    AdminRoomSlotTemplateCreate,
    AdminRoomSlotTemplateItem,
    AdminRoomSlotTemplateList,
    AdminRoomSlotTemplatePages,
    AdminRoomSlotTemplateUpdate,
)
from portal.serializers.admin.v1.facility.translation import (
    AdminFacilityTranslationInput,
    AdminFacilityTranslationItem,
)
from portal.serializers.mixins import DeleteBaseModel, GenericQueryBaseModel


def pages_query_to_command(model: GenericQueryBaseModel) -> PagesQueryCommand:
    return PagesQueryCommand(
        page=model.page,
        page_size=model.page_size,
        order_by=model.order_by,
        descending=model.descending,
        deleted=model.deleted,
        keyword=model.keyword,
    )


def delete_model_to_command(model: DeleteBaseModel) -> DeleteCommand:
    return DeleteCommand(reason=model.reason, permanent=model.permanent)


def bulk_action_to_command(model: AdminRoomBulkAction) -> BulkIdsCommand:
    return BulkIdsCommand(ids=model.ids)


def _translation_commands(
    translations: list[AdminFacilityTranslationInput] | None,
) -> list[FacilityTranslationCommand] | None:
    if translations is None:
        return None
    return [
        FacilityTranslationCommand(
            locale_id=item.locale_id,
            name=item.name,
            description=item.description,
            remark=item.remark,
        )
        for item in translations
    ]


def _translation_items_to_api(items: list[TranslationItemResult]) -> list[AdminFacilityTranslationItem]:
    return [
        AdminFacilityTranslationItem(
            locale_id=item.locale_id,
            name=item.name,
            description=item.description,
            remark=item.remark,
        )
        for item in items
    ]


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
    )


def update_room_to_command(model: AdminRoomUpdate) -> UpdateRoomCommand:
    return UpdateRoomCommand(
        name=model.name,
        room_number=model.room_number,
        capacity=model.capacity,
        is_active=model.is_active,
        sequence=model.sequence,
        translations=_translation_commands(model.translations),
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
    )


def room_page_result_to_api(result: RoomPageResult) -> AdminRoomPages:
    return AdminRoomPages(
        page=result.page,
        page_size=result.page_size,
        total=result.total,
        items=[room_detail_to_api(item) for item in result.items],
    )


def room_list_result_to_api(result: RoomListResult) -> AdminRoomList:
    from portal.serializers.admin.v1.facility.room import AdminRoomBase

    return AdminRoomList(
        items=[
            AdminRoomBase(id=item.id, code=item.code, name=item.name)
            for item in result.items
        ]
    )


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
        page=result.page,
        page_size=result.page_size,
        total=result.total,
        items=[room_slot_template_to_api(item) for item in result.items],
    )


def room_slot_template_list_to_api(result: RoomSlotTemplateListResult) -> AdminRoomSlotTemplateList:
    return AdminRoomSlotTemplateList(items=[room_slot_template_to_api(item) for item in result.items])


def room_slot_template_pages_query_to_command(model) -> tuple[PagesQueryCommand, UUID | None]:
    from portal.serializers.admin.v1.facility.room_slot_template import AdminRoomSlotTemplateQuery

    base = pages_query_to_command(model)
    if not isinstance(model, AdminRoomSlotTemplateQuery):
        return base, None
    return base, model.facility_id


def create_rental_rate_to_command(model: AdminRentalRateCreate) -> CreateRentalRateCommand:
    return CreateRentalRateCommand(
        facility_id=model.facility_id,
        billing_unit=model.billing_unit,
        unit_amount=model.unit_amount,
        currency=model.currency,
        is_default=model.is_default,
        is_active=model.is_active,
        effective_from=model.effective_from,
        effective_to=model.effective_to,
        sequence=model.sequence,
        name=model.name,
        translations=_translation_commands(model.translations),
    )


def update_rental_rate_to_command(model: AdminRentalRateUpdate) -> UpdateRentalRateCommand:
    return UpdateRentalRateCommand(
        facility_id=model.facility_id,
        billing_unit=model.billing_unit,
        unit_amount=model.unit_amount,
        currency=model.currency,
        is_default=model.is_default,
        is_active=model.is_active,
        effective_from=model.effective_from,
        effective_to=model.effective_to,
        sequence=model.sequence,
        name=model.name,
        translations=_translation_commands(model.translations),
    )


def rental_rate_to_api(result: RentalRateResult) -> AdminRentalRateItem:
    return AdminRentalRateItem(
        id=result.id,
        facility_id=result.facility_id,
        billing_unit=result.billing_unit,
        unit_amount=result.unit_amount,
        currency=result.currency,
        is_default=result.is_default,
        is_active=result.is_active,
        effective_from=result.effective_from,
        effective_to=result.effective_to,
        sequence=result.sequence,
        remark=result.remark,
        name=result.name,
        created_at=result.created_at,
        created_by=result.created_by,
        updated_at=result.updated_at,
        updated_by=result.updated_by,
        delete_reason=result.delete_reason,
        translations=_translation_items_to_api(result.translations),
    )


def rental_rate_page_to_api(result: RentalRatePageResult) -> AdminRentalRatePages:
    return AdminRentalRatePages(
        page=result.page,
        page_size=result.page_size,
        total=result.total,
        items=[rental_rate_to_api(item) for item in result.items],
    )


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
        room_lines=[
            PreviewQuoteRoomLineCommand(
                facility_id=line.facility_id,
                billed_hours=line.billed_hours,
            )
            for line in model.room_lines
        ],
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
                pricing_tier_used=line.pricing_tier_used,
                rental_rate_id=line.rental_rate_id,
                line_subtotal=line.line_subtotal,
            )
            for line in result.room_lines
        ],
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


def update_policy_setting_to_command(model: AdminPolicySettingUpdate) -> UpdatePolicySettingCommand:
    return UpdatePolicySettingCommand.model_validate(model.model_dump())


def policy_setting_to_api(result: PolicySettingResult) -> AdminPolicySettingItem:
    return AdminPolicySettingItem.model_validate(result.model_dump())


def policy_setting_list_to_api(result: PolicySettingListResult) -> AdminPolicySettingList:
    return AdminPolicySettingList(items=[policy_setting_to_api(item) for item in result.items])


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


def member_pages_query_to_command(model) -> "MemberPagesQueryCommand":
    from portal.application.facility.commands import MemberPagesQueryCommand
    from portal.serializers.admin.v1.facility.member import AdminMemberQuery

    base = pages_query_to_command(model)
    if not isinstance(model, AdminMemberQuery):
        return MemberPagesQueryCommand(**base.model_dump())
    return MemberPagesQueryCommand(**base.model_dump(), ministry_id=model.ministry_id)


def override_log_pages_query_to_command(model) -> "OverrideLogPagesQueryCommand":
    from portal.application.facility.commands import OverrideLogPagesQueryCommand
    from portal.serializers.admin.v1.facility.override_log import AdminOverrideLogQuery

    base = pages_query_to_command(model)
    if not isinstance(model, AdminOverrideLogQuery):
        return OverrideLogPagesQueryCommand(**base.model_dump())
    return OverrideLogPagesQueryCommand(
        **base.model_dump(),
        facility_id=model.facility_id,
        overridden_by_id=model.overridden_by_id,
        date_from=model.date_from,
        date_to=model.date_to,
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
            BookingRoomLineCommand(
                facility_id=room.facility_id,
                start_at=room.start_at,
                end_at=room.end_at,
                sequence=room.sequence,
            )
            for room in model.rooms
        ],
        surcharge_codes=model.surcharge_codes,
    )


def cancel_booking_to_command(model) -> "CancelBookingCommand":
    from portal.application.facility.commands import CancelBookingCommand

    return CancelBookingCommand(scope=model.scope, cancel_reason=model.cancel_reason)


def replace_member_ministries_to_command(model) -> "ReplaceMinistryMemberCommand":
    from portal.application.facility.commands import ReplaceMinistryMemberCommand
    from portal.serializers.admin.v1.facility.member import AdminMemberMinistriesUpdate

    return ReplaceMinistryMemberCommand(ministry_ids=model.ministry_ids)


def booking_page_to_api(result) -> "AdminBookingPages":
    from portal.serializers.admin.v1.facility.booking import AdminBookingDetail, AdminBookingPages

    return AdminBookingPages(
        page=result.page,
        page_size=result.page_size,
        total=result.total,
        items=[AdminBookingDetail.model_validate(item.model_dump()) for item in result.items],
    )


def booking_detail_to_api(result) -> "AdminBookingDetail":
    from portal.serializers.admin.v1.facility.booking import AdminBookingDetail

    return AdminBookingDetail.model_validate(result.model_dump())


def member_page_to_api(result) -> "AdminMemberPages":
    from portal.serializers.admin.v1.facility.member import AdminMemberPages

    return AdminMemberPages(
        page=result.page,
        page_size=result.page_size,
        total=result.total,
        items=[item for item in result.items],
    )


def member_detail_to_api(result) -> "AdminMemberDetail":
    from portal.serializers.admin.v1.facility.member import AdminMemberDetail

    return AdminMemberDetail.model_validate(result.model_dump())


def override_log_page_to_api(result) -> "AdminOverrideLogPages":
    from portal.serializers.admin.v1.facility.override_log import AdminOverrideLogPages

    return AdminOverrideLogPages(
        page=result.page,
        page_size=result.page_size,
        total=result.total,
        items=[item for item in result.items],
    )
