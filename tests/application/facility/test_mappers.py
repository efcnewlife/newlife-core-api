"""
Facility mapper tests (serializer <-> command/result).
"""
from datetime import datetime, time, timezone
from decimal import Decimal
from uuid import uuid4

from portal.application.facility.mappers import (
    booking_pages_query_to_command,
    bulk_action_to_command,
    cancel_booking_to_command,
    create_discount_rule_to_command,
    create_rental_rate_to_command,
    create_room_slot_template_to_command,
    create_room_to_command,
    create_surcharge_to_command,
    delete_model_to_command,
    discount_rule_to_api,
    member_pages_query_to_command,
    override_log_pages_query_to_command,
    pages_query_to_command,
    preview_quote_result_to_api,
    preview_quote_to_command,
    replace_member_ministries_to_command,
    room_detail_to_api,
    update_booking_to_command,
    update_policy_setting_to_command,
)
from portal.application.org.mappers import (
    create_ministry_to_command,
    ministry_detail_to_api,
    replace_ministry_members_to_command,
)
from portal.application.facility.results import (
    DiscountRuleResult,
    PreviewQuoteResult,
    PreviewQuoteRoomLineResult,
    RoomDetailResult,
    TranslationItemResult,
)
from portal.application.org.results import MinistryDetailResult
from portal.domain.facility.constants import BookingType, RentalRateBillingUnit
from portal.serializers.admin.v1.facility.booking import AdminBookingCancel, AdminBookingQuery, AdminBookingUpdate
from portal.serializers.admin.v1.facility.member import AdminMemberMinistriesUpdate, AdminMemberQuery
from portal.serializers.admin.v1.facility.override_log import AdminOverrideLogQuery
from portal.serializers.admin.v1.facility.rental_catalog import (
    AdminDiscountRuleCreate,
    AdminPolicySettingUpdate,
    AdminSurchargeCreate,
)
from portal.serializers.admin.v1.facility.rental_rate import (
    AdminPreviewQuoteRequest,
    AdminPreviewQuoteRoomLine,
    AdminRentalRateCreate,
)
from portal.serializers.admin.v1.facility.room import AdminRoomBulkAction, AdminRoomCreate
from portal.serializers.admin.v1.facility.room_slot_template import AdminRoomSlotTemplateCreate
from portal.serializers.admin.v1.facility.translation import AdminFacilityTranslationInput
from portal.domain.org.constants import MinistryMemberRole
from portal.serializers.admin.v1.ministry import (
    AdminMinistryCreate,
    AdminMinistryMemberInput,
    AdminMinistryReplaceMembers,
)
from portal.serializers.admin.v1.org.translation import AdminOrgTranslationInput
from portal.serializers.mixins import DeleteBaseModel, GenericQueryBaseModel


def test_pages_query_to_command():
    model = GenericQueryBaseModel(page=2, page_size=25, keyword="gym")
    command = pages_query_to_command(model)
    assert command.page == 2
    assert command.page_size == 25
    assert command.keyword == "gym"


def test_delete_model_to_command():
    model = DeleteBaseModel(reason="cleanup", permanent=True)
    command = delete_model_to_command(model)
    assert command.reason == "cleanup"
    assert command.permanent is True


def test_bulk_action_to_command():
    room_id = uuid4()
    command = bulk_action_to_command(AdminRoomBulkAction(ids=[room_id]))
    assert command.ids == [room_id]


def test_create_room_to_command_with_translations():
    locale_id = uuid4()
    model = AdminRoomCreate(
        code="gym-a",
        name="Gym A",
        translations=[
            AdminFacilityTranslationInput(locale_id=locale_id, name="Gym A"),
        ],
    )
    command = create_room_to_command(model)
    assert command.code == "gym-a"
    assert command.translations[0].locale_id == locale_id


def test_room_detail_to_api_round_trip_key_fields():
    room_id = uuid4()
    locale_id = uuid4()
    result = RoomDetailResult(
        id=room_id,
        code="gym-a",
        name="Gym A",
        translations=[TranslationItemResult(locale_id=locale_id, name="Gym A")],
    )
    api = room_detail_to_api(result)
    assert api.id == room_id
    assert api.code == "gym-a"
    assert len(api.translations) == 1


def test_preview_quote_to_command():
    facility_id = uuid4()
    model = AdminPreviewQuoteRequest(
        booking_type=BookingType.RECURRING.value,
        is_mission_aligned=True,
        room_lines=[AdminPreviewQuoteRoomLine(facility_id=facility_id, billed_hours=Decimal("6"))],
        surcharge_codes=["audio_system"],
    )
    command = preview_quote_to_command(model)
    assert command.booking_type == BookingType.RECURRING
    assert command.is_mission_aligned is True
    assert command.room_lines[0].facility_id == facility_id
    assert command.room_lines[0].billed_hours == Decimal("6")
    assert command.surcharge_codes == ["audio_system"]


def test_preview_quote_result_to_api():
    facility_id = uuid4()
    result = PreviewQuoteResult(
        subtotal_amount=Decimal("100"),
        discount_percent=Decimal("20"),
        discount_amount=Decimal("20"),
        surcharge_amount=Decimal("5"),
        quoted_amount=Decimal("85"),
        currency="CAD",
        room_lines=[
            PreviewQuoteRoomLineResult(
                facility_id=facility_id,
                billed_hours=Decimal("6"),
                pricing_tier_used=RentalRateBillingUnit.DAILY_FLAT.value,
                line_subtotal=Decimal("100"),
            ),
        ],
    )
    api = preview_quote_result_to_api(result)
    assert api.quoted_amount == Decimal("85")
    assert api.room_lines[0].pricing_tier_used == RentalRateBillingUnit.DAILY_FLAT.value


def test_create_rental_rate_to_command():
    facility_id = uuid4()
    locale_id = uuid4()
    model = AdminRentalRateCreate(
        facility_id=facility_id,
        billing_unit=RentalRateBillingUnit.HOURLY,
        unit_amount=Decimal("15"),
        translations=[AdminFacilityTranslationInput(locale_id=locale_id, name="Hourly Rate")],
    )
    command = create_rental_rate_to_command(model)
    assert command.facility_id == facility_id
    assert command.unit_amount == Decimal("15")
    assert command.translations[0].locale_id == locale_id


def test_create_room_slot_template_to_command():
    facility_id = uuid4()
    model = AdminRoomSlotTemplateCreate(
        facility_id=facility_id,
        name="Morning",
        days_of_week=[0, 1, 2],
        start_time=time(9, 0),
        end_time=time(12, 0),
        slot_duration_minutes=60,
    )
    command = create_room_slot_template_to_command(model)
    assert command.facility_id == facility_id
    assert command.days_of_week == [0, 1, 2]
    assert command.start_time == time(9, 0)


def test_room_slot_template_to_api_decodes_mask():
    from portal.application.facility.mappers import room_slot_template_to_api
    from portal.application.facility.results import RoomSlotTemplateResult

    facility_id = uuid4()
    result = RoomSlotTemplateResult(
        id=uuid4(),
        facility_id=facility_id,
        name="Morning",
        days_of_week_mask=31,
        start_time=time(9, 0),
        end_time=time(12, 0),
        slot_duration_minutes=60,
        is_active=True,
    )
    item = room_slot_template_to_api(result)
    assert item.days_of_week == [0, 1, 2, 3, 4]


def test_catalog_mappers():
    discount = AdminDiscountRuleCreate(code="mission_aligned", percent_off=Decimal("30"))
    command = create_discount_rule_to_command(discount)
    assert command.percent_off == Decimal("30")

    surcharge = AdminSurchargeCreate(
        code="audio_system",
        charge_type="flat",
        unit_amount=Decimal("25"),
    )
    surcharge_cmd = create_surcharge_to_command(surcharge)
    assert surcharge_cmd.unit_amount == Decimal("25")

    policy = AdminPolicySettingUpdate(amount="100", currency="CAD")
    policy_cmd = update_policy_setting_to_command(policy)
    assert policy_cmd.amount == Decimal("100")

    rule_result = DiscountRuleResult(
        id=uuid4(),
        code="mission_aligned",
        percent_off=Decimal("30"),
    )
    api_rule = discount_rule_to_api(rule_result)
    assert api_rule.code == "mission_aligned"


def test_ministry_mappers():
    locale_id = uuid4()
    model = AdminMinistryCreate(
        name="Youth",
        translations=[AdminOrgTranslationInput(locale_id=locale_id, name="Youth")],
    )
    command = create_ministry_to_command(model)
    assert command.name == "Youth"

    detail = MinistryDetailResult(id=uuid4(), name="Youth", status="draft")
    api = ministry_detail_to_api(detail)
    assert api.name == "Youth"
    assert api.status == "draft"

    assign_cmd = replace_ministry_members_to_command(
        AdminMinistryReplaceMembers(
            members=[
                AdminMinistryMemberInput(user_id=uuid4(), member_role=MinistryMemberRole.SECONDARY),
            ]
        )
    )
    assert len(assign_cmd.members) == 1


def test_booking_and_member_mappers():
    facility_id = uuid4()
    booking_query = AdminBookingQuery(
        page=1,
        page_size=20,
        facility_id=facility_id,
        status="confirmed",
    )
    booking_cmd = booking_pages_query_to_command(booking_query)
    assert booking_cmd.facility_id == facility_id
    assert booking_cmd.status == "confirmed"

    start = datetime(2026, 5, 1, 10, 0, tzinfo=timezone.utc)
    end = datetime(2026, 5, 1, 14, 0, tzinfo=timezone.utc)
    from portal.serializers.admin.v1.facility.booking import AdminBookingRoomInput

    update_model = AdminBookingUpdate(
        start_at=start,
        end_at=end,
        is_mission_aligned=True,
        rooms=[AdminBookingRoomInput(facility_id=facility_id, sequence=0)],
        surcharge_codes=["audio_system"],
    )
    update_cmd = update_booking_to_command(update_model)
    assert update_cmd.is_mission_aligned is True
    assert update_cmd.rooms[0].facility_id == facility_id

    cancel_cmd = cancel_booking_to_command(AdminBookingCancel(scope="series", cancel_reason="weather"))
    assert cancel_cmd.scope == "series"
    assert cancel_cmd.cancel_reason == "weather"

    member_query = AdminMemberQuery(page=1, page_size=10, ministry_id=uuid4())
    member_cmd = member_pages_query_to_command(member_query)
    assert member_cmd.ministry_id is not None

    ministry_ids = [uuid4()]
    replace_cmd = replace_member_ministries_to_command(
        AdminMemberMinistriesUpdate(ministry_ids=ministry_ids)
    )
    assert replace_cmd.ministry_ids == ministry_ids


def test_override_log_pages_query_to_command():
    facility_id = uuid4()
    query = AdminOverrideLogQuery(page=1, page_size=10, facility_id=facility_id)
    command = override_log_pages_query_to_command(query)
    assert command.facility_id == facility_id
