"""
Facility mapper tests (serializer <-> command/result).
"""

from datetime import date, datetime, time, timezone
from decimal import Decimal
from inspect import getsource
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError

from portal.application.facility.mappers import (
    blackout_impact_to_api,
    booking_detail_to_api,
    booking_page_to_api,
    booking_pages_query_to_command,
    booking_range_to_api,
    bulk_action_to_command,
    cancel_booking_to_command,
    cancel_recurring_booking_series_to_command,
    create_discount_rule_to_command,
    create_recurring_booking_series_to_command,
    create_rental_rate_to_command,
    create_room_blackout_to_command,
    create_room_slot_template_to_command,
    create_room_to_command,
    create_surcharge_to_command,
    delete_model_to_command,
    discount_rule_to_api,
    member_booking_detail_to_api,
    member_browse_booking_to_api,
    member_preview_quote_result_to_api,
    member_preview_quote_to_command,
    override_log_pages_query_to_command,
    pages_query_to_command,
    pending_payment_series_list_to_admin_api,
    preview_quote_result_to_api,
    preview_quote_to_command,
    recurring_booking_preview_to_member_api,
    recurring_booking_series_to_admin_api,
    recurring_booking_series_to_member_api,
    room_availability_item_to_api,
    room_detail_to_api,
    update_booking_to_command,
)
from portal.application.facility.participant_detail import assemble_participant_booking_detail
from portal.application.facility.results import (
    BlackoutImpactOccurrenceResult,
    BlackoutImpactResult,
    BookingDetailResult,
    BookingListItemResult,
    BookingPageResult,
    BookingRangeResult,
    BookingRoomLineResult,
    DayAvailabilityResult,
    DiscountRuleResult,
    MemberBrowseBookingResult,
    PendingPaymentSeriesListItemResult,
    PendingPaymentSeriesListResult,
    PreviewQuoteResult,
    PreviewQuoteRoomLineResult,
    RecurringBookingConflictResult,
    RecurringBookingOccurrenceResult,
    RecurringBookingPreviewResult,
    RecurringBookingSeriesResult,
    RoomAvailabilityResult,
    RoomDetailResult,
    TranslationItemResult,
)
from portal.application.org.mappers import create_ministry_to_command, ministry_detail_to_api, replace_ministry_members_to_command
from portal.application.org.results import MinistryDetailResult
from portal.domain.facility.constants import BookingType, RecurringConflictKind, RentalRateBillingUnit
from portal.domain.org.constants import MinistryMemberRole
from portal.infrastructure.persistence.repositories.facility.booking_repository import BookingRepository
from portal.infrastructure.persistence.repositories.facility.recurring_booking_repository import RecurringBookingRepository
from portal.serializers.admin.v1.facility.booking import AdminBookingCancel, AdminBookingQuery, AdminBookingUpdate
from portal.serializers.admin.v1.facility.override_log import AdminOverrideLogQuery
from portal.serializers.admin.v1.facility.rental_catalog import AdminDiscountRuleCreate, AdminSurchargeCreate
from portal.serializers.admin.v1.facility.rental_rate import AdminPreviewQuoteRequest, AdminPreviewQuoteRoomLine, AdminRentalRateCreate
from portal.serializers.admin.v1.facility.room import AdminRoomBulkAction, AdminRoomCreate
from portal.serializers.admin.v1.facility.room_blackout import AdminRoomBlackoutCreate
from portal.serializers.admin.v1.facility.room_slot_template import AdminRoomSlotTemplateCreate
from portal.serializers.admin.v1.facility.translation import AdminFacilityTranslationInput
from portal.serializers.admin.v1.ministry import AdminMinistryCreate, AdminMinistryMemberInput, AdminMinistryReplaceMembers
from portal.serializers.admin.v1.org.translation import AdminOrgTranslationInput
from portal.serializers.apis.v1.facility import (
    MemberPreviewQuoteLineInput,
    MemberPreviewQuoteRequest,
    MemberRecurringBookingSeriesCancel,
    MemberRecurringBookingSeriesCreate,
    MemberRecurringBookingSeriesProposal,
    MemberRecurringBookingSeriesRoomInput,
)
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
    model = AdminRoomCreate(code="gym-a", name="Gym A", translations=[AdminFacilityTranslationInput(locale_id=locale_id, name="Gym A")])
    command = create_room_to_command(model)
    assert command.code == "gym-a"
    assert command.translations[0].locale_id == locale_id


def test_room_detail_to_api_round_trip_key_fields():
    room_id = uuid4()
    locale_id = uuid4()
    result = RoomDetailResult(id=room_id, code="gym-a", name="Gym A", translations=[TranslationItemResult(locale_id=locale_id, name="Gym A")])
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
                rental_rate_name="Daily flat",
                billing_unit=RentalRateBillingUnit.DAILY_FLAT.value,
                unit_amount=Decimal("100"),
                currency="CAD",
                applicability={"all": [{"op": "hours_gte", "value": 5}]},
                is_default=False,
                line_subtotal=Decimal("100"),
            )
        ],
    )
    api = preview_quote_result_to_api(result)
    assert api.quoted_amount == Decimal("85")
    assert api.room_lines[0].billing_unit == RentalRateBillingUnit.DAILY_FLAT.value
    assert api.room_lines[0].rental_rate_name == "Daily flat"


def test_create_rental_rate_to_command():
    facility_id = uuid4()
    template_id = uuid4()
    model = AdminRentalRateCreate(facility_id=facility_id, template_id=template_id, is_active=True)
    command = create_rental_rate_to_command(model)
    assert command.facility_id == facility_id
    assert command.template_id == template_id
    assert command.is_active is True


def test_create_room_slot_template_to_command():
    facility_id = uuid4()
    model = AdminRoomSlotTemplateCreate(
        facility_id=facility_id, name="Morning", days_of_week=[0, 1, 2], start_time=time(9, 0), end_time=time(12, 0), slot_duration_minutes=60
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

    surcharge = AdminSurchargeCreate(code="audio_system", charge_type="flat", unit_amount=Decimal("25"))
    surcharge_cmd = create_surcharge_to_command(surcharge)
    assert surcharge_cmd.unit_amount == Decimal("25")

    rule_result = DiscountRuleResult(id=uuid4(), code="mission_aligned", percent_off=Decimal("30"))
    api_rule = discount_rule_to_api(rule_result)
    assert api_rule.code == "mission_aligned"


def test_ministry_mappers():
    locale_id = uuid4()
    model = AdminMinistryCreate(name="Youth", translations=[AdminOrgTranslationInput(locale_id=locale_id, name="Youth")])
    command = create_ministry_to_command(model)
    assert command.name == "Youth"

    detail = MinistryDetailResult(id=uuid4(), name="Youth", status="draft")
    api = ministry_detail_to_api(detail)
    assert api.name == "Youth"
    assert api.status == "draft"

    assign_cmd = replace_ministry_members_to_command(
        AdminMinistryReplaceMembers(members=[AdminMinistryMemberInput(user_id=uuid4(), member_role=MinistryMemberRole.SECONDARY)])
    )
    assert len(assign_cmd.members) == 1


def test_booking_and_member_mappers():
    facility_id = uuid4()
    booking_query = AdminBookingQuery(page=1, page_size=20, facility_id=facility_id, status="confirmed")
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


def test_booking_page_to_api_includes_ordered_facility_ids():
    primary_id = uuid4()
    secondary_id = uuid4()
    start = datetime(2026, 5, 1, 10, 0, tzinfo=timezone.utc)
    end = datetime(2026, 5, 1, 12, 0, tzinfo=timezone.utc)
    item = BookingListItemResult(
        id=uuid4(),
        user_id=uuid4(),
        facility_id=primary_id,
        facility_ids=[primary_id, secondary_id],
        facility_names=["Gym", "Hall"],
        booking_type="one_time",
        start_at=start,
        end_at=end,
        status="confirmed",
    )
    api = booking_page_to_api(BookingPageResult(page=0, page_size=20, total=1, items=[item]))
    assert api.items[0].facility_id == primary_id
    assert api.items[0].facility_ids == [primary_id, secondary_id]
    assert api.items[0].model_dump(by_alias=True)["facilityIds"] == [primary_id, secondary_id]


def test_booking_page_to_api_keeps_empty_facility_ids_and_primary():
    primary_id = uuid4()
    start = datetime(2026, 5, 1, 10, 0, tzinfo=timezone.utc)
    end = datetime(2026, 5, 1, 12, 0, tzinfo=timezone.utc)
    item = BookingListItemResult(
        id=uuid4(),
        user_id=uuid4(),
        facility_id=primary_id,
        facility_ids=[],
        facility_names=[],
        booking_type="one_time",
        start_at=start,
        end_at=end,
        status="confirmed",
    )
    api = booking_page_to_api(BookingPageResult(page=0, page_size=20, total=1, items=[item]))
    assert api.items[0].facility_id == primary_id
    assert api.items[0].facility_ids == []


def test_group_facility_lines_preserves_room_line_order():
    booking_a = uuid4()
    booking_b = uuid4()
    room_1 = uuid4()
    room_2 = uuid4()
    room_3 = uuid4()
    ids_by_booking, names_by_booking = BookingRepository.group_facility_lines(
        [
            {"facility_booking_id": booking_a, "facility_id": room_2, "facility_name": "B"},
            {"facility_booking_id": booking_a, "facility_id": room_1, "facility_name": "A"},
            {"facility_booking_id": booking_b, "facility_id": room_3, "facility_name": "C"},
            {"facility_booking_id": booking_b, "facility_id": room_3, "facility_name": None},
        ]
    )
    assert ids_by_booking[booking_a] == [room_2, room_1]
    assert names_by_booking[booking_a] == ["B", "A"]
    assert ids_by_booking[booking_b] == [room_3, room_3]
    assert names_by_booking[booking_b] == ["C"]


def test_override_log_pages_query_to_command():
    facility_id = uuid4()
    query = AdminOverrideLogQuery(page=1, page_size=10, facility_id=facility_id)
    command = override_log_pages_query_to_command(query)
    assert command.facility_id == facility_id


def test_member_preview_quote_to_command_maps_per_line_intervals():
    facility_id = uuid4()
    line_one_start = datetime(2026, 8, 22, 14, 0, tzinfo=timezone.utc)
    line_one_end = datetime(2026, 8, 22, 16, 0, tzinfo=timezone.utc)
    line_two_start = datetime(2026, 8, 22, 18, 0, tzinfo=timezone.utc)
    line_two_end = datetime(2026, 8, 22, 22, 0, tzinfo=timezone.utc)
    model = MemberPreviewQuoteRequest(
        is_mission_aligned=True,
        surcharge_codes=["audio_system"],
        lines=[
            MemberPreviewQuoteLineInput(facility_id=facility_id, start_at=line_one_start, end_at=line_one_end),
            MemberPreviewQuoteLineInput(facility_id=facility_id, start_at=line_two_start, end_at=line_two_end),
        ],
    )
    command = member_preview_quote_to_command(model)
    assert command.is_mission_aligned is True
    assert command.ministry_id is None
    assert command.surcharge_codes == ["audio_system"]
    assert command.lines[0].facility_id == facility_id
    assert command.lines[0].start_at == line_one_start
    assert command.lines[0].end_at == line_one_end
    assert command.lines[1].start_at == line_two_start
    assert command.lines[1].end_at == line_two_end


def test_member_preview_quote_result_to_api_includes_money_fields():
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
                billed_hours=Decimal("4"),
                rental_rate_name="Daily flat",
                billing_unit=RentalRateBillingUnit.DAILY_FLAT.value,
                unit_amount=Decimal("100"),
                currency="CAD",
                applicability={"all": [{"op": "hours_gte", "value": 5}]},
                is_default=False,
                line_subtotal=Decimal("100"),
            )
        ],
    )
    api = member_preview_quote_result_to_api(result)
    dumped = api.model_dump(by_alias=True)
    assert dumped["quotedAmount"] == Decimal("85")
    assert dumped["discountAmount"] == Decimal("20")
    assert dumped["surchargeAmount"] == Decimal("5")
    assert dumped["currency"] == "CAD"
    assert dumped["roomLines"][0]["facilityId"] == facility_id


def test_room_availability_item_to_api_includes_photo_urls():
    room_id = uuid4()
    item = RoomAvailabilityResult(id=room_id, code="gym", name="Gym", photo_urls=["https://cdn.example/a.jpg"], availability=DayAvailabilityResult())
    api = room_availability_item_to_api(item)
    dumped = api.model_dump(by_alias=True)
    assert dumped["photoUrls"] == ["https://cdn.example/a.jpg"]


def test_member_preview_quote_maps_three_lines_with_distinct_intervals():
    rooms = [uuid4(), uuid4(), uuid4()]
    model = MemberPreviewQuoteRequest(
        lines=[
            MemberPreviewQuoteLineInput(
                facility_id=room_id, start_at=datetime(2026, 8, 22, 9, 0, tzinfo=timezone.utc), end_at=datetime(2026, 8, 22, 11, 0, tzinfo=timezone.utc)
            )
            for room_id in rooms
        ]
    )
    command = member_preview_quote_to_command(model)
    assert [line.facility_id for line in command.lines] == rooms
    assert all(line.end_at > line.start_at for line in command.lines)


def test_member_preview_quote_rejects_empty_and_more_than_three_lines():
    interval = dict(start_at=datetime(2026, 8, 22, 14, 0, tzinfo=timezone.utc), end_at=datetime(2026, 8, 22, 18, 0, tzinfo=timezone.utc))
    with pytest.raises(ValidationError):
        MemberPreviewQuoteRequest(lines=[])
    with pytest.raises(ValidationError):
        MemberPreviewQuoteRequest(
            lines=[
                MemberPreviewQuoteLineInput(facility_id=uuid4(), **interval),
                MemberPreviewQuoteLineInput(facility_id=uuid4(), **interval),
                MemberPreviewQuoteLineInput(facility_id=uuid4(), **interval),
                MemberPreviewQuoteLineInput(facility_id=uuid4(), **interval),
            ]
        )


def test_member_booking_detail_to_api_includes_quoted_amount():
    booking_id = uuid4()
    room_id = uuid4()
    viewer_id = uuid4()
    start = datetime(2026, 8, 22, 14, 0, tzinfo=timezone.utc)
    end = datetime(2026, 8, 22, 18, 0, tzinfo=timezone.utc)
    result = BookingDetailResult(
        id=booking_id,
        user_id=viewer_id,
        booking_type="one_time",
        start_at=start,
        end_at=end,
        status="confirmed",
        quoted_amount=Decimal("85"),
        currency="CAD",
        rooms=[BookingRoomLineResult(id=uuid4(), facility_id=room_id, facility_name="Gym", start_at=start, end_at=end)],
    )
    api = member_booking_detail_to_api(
        assemble_participant_booking_detail(result, viewer_id=viewer_id, now=start, facility_tz=ZoneInfo("America/Toronto"), photo_urls_by_room={})
    )
    dumped = api.model_dump(by_alias=True)
    assert dumped["quotedAmount"] == Decimal("85")
    assert dumped["currency"] == "CAD"
    assert dumped["rooms"][0]["facilityId"] == room_id


def test_create_recurring_booking_series_to_command_maps_excluded_dates():
    model = MemberRecurringBookingSeriesCreate(
        title="Weekly choir",
        first_occurrence_date=date(2026, 1, 6),
        last_occurrence_date=date(2026, 2, 10),
        local_start_time=time(10, 0),
        local_end_time=time(12, 0),
        rooms=[MemberRecurringBookingSeriesRoomInput(facility_id=uuid4(), sequence=0)],
        excluded_dates=[date(2026, 1, 13)],
    )
    command = create_recurring_booking_series_to_command(model)
    assert command.excluded_dates == [date(2026, 1, 13)]


def test_create_recurring_booking_series_to_command_preview_proposal_has_no_exclusions():
    model = MemberRecurringBookingSeriesProposal(
        first_occurrence_date=date(2026, 1, 6),
        last_occurrence_date=date(2026, 2, 10),
        local_start_time=time(10, 0),
        local_end_time=time(12, 0),
        rooms=[MemberRecurringBookingSeriesRoomInput(facility_id=uuid4(), sequence=0)],
    )
    command = create_recurring_booking_series_to_command(model)
    assert command.excluded_dates == []


def test_recurring_booking_preview_to_member_api_uses_camel_case():
    room_id = uuid4()
    result = RecurringBookingPreviewResult(
        conflicts=[RecurringBookingConflictResult(occurrence_date=date(2026, 1, 13), kind=RecurringConflictKind.OCCUPANCY.value, facility_ids=[room_id])]
    )
    api = recurring_booking_preview_to_member_api(result)
    dumped = api.model_dump(by_alias=True)
    assert dumped["conflicts"][0]["occurrenceDate"] == date(2026, 1, 13)
    assert dumped["conflicts"][0]["kind"] == "occupancy"
    assert dumped["conflicts"][0]["facilityIds"] == [room_id]
    assert dumped["conflicts"][0]["isOverridable"] is False
    assert dumped["conflicts"][0]["ministryStewardDisplayName"] is None


def test_recurring_booking_preview_includes_ministry_steward_contact():
    room_id = uuid4()
    ministry_id = uuid4()
    result = RecurringBookingPreviewResult(
        conflicts=[
            RecurringBookingConflictResult(
                occurrence_date=date(2026, 1, 13),
                kind=RecurringConflictKind.MINISTRY.value,
                facility_ids=[room_id],
                ministry_id=ministry_id,
                ministry_steward_display_name="Primary Steward",
                ministry_steward_email="steward@efcnewlife.org",
            )
        ]
    )
    dumped = recurring_booking_preview_to_member_api(result).model_dump(by_alias=True)
    assert dumped["conflicts"][0]["kind"] == "ministry"
    assert dumped["conflicts"][0]["ministryId"] == ministry_id
    assert dumped["conflicts"][0]["ministryStewardDisplayName"] == "Primary Steward"
    assert dumped["conflicts"][0]["ministryStewardEmail"] == "steward@efcnewlife.org"


def test_pending_payment_series_list_to_admin_api_uses_camel_case():
    series_id = uuid4()
    user_id = uuid4()
    ministry_id = uuid4()
    expires_at = datetime(2026, 1, 13, 17, 0, tzinfo=timezone.utc)
    result = PendingPaymentSeriesListResult(
        items=[
            PendingPaymentSeriesListItemResult(
                id=series_id,
                user_id=user_id,
                user_email="booker@efcnewlife.org",
                user_display_name="Jane Booker",
                ministry_id=ministry_id,
                ministry_name="Youth Fellowship",
                quoted_amount=Decimal("240"),
                currency="CAD",
                occurrence_count=4,
                payment_hold_expires_at=expires_at,
                is_priority=True,
            )
        ]
    )
    dumped = pending_payment_series_list_to_admin_api(result).model_dump(by_alias=True)
    item = dumped["items"][0]
    assert item["id"] == str(series_id)
    assert item["userId"] == user_id
    assert item["userEmail"] == "booker@efcnewlife.org"
    assert item["userDisplayName"] == "Jane Booker"
    assert item["ministryId"] == ministry_id
    assert item["ministryName"] == "Youth Fellowship"
    assert item["quotedAmount"] == Decimal("240")
    assert item["currency"] == "CAD"
    assert item["occurrenceCount"] == 4
    assert item["paymentHoldExpiresAt"] == expires_at
    assert item["isPriority"] is True


def test_cancel_recurring_booking_series_to_command():
    occurrence_id = uuid4()
    command = cancel_recurring_booking_series_to_command(
        MemberRecurringBookingSeriesCancel(scope="this_and_future", occurrence_id=occurrence_id, cancel_reason="moving")
    )
    assert command.scope == "this_and_future"
    assert command.occurrence_id == occurrence_id
    assert command.cancel_reason == "moving"


def test_recurring_booking_series_to_member_api_exposes_occurrence_and_payment_state():
    expires_at = datetime(2026, 3, 12, 17, 0, tzinfo=timezone.utc)
    occurrence_id = uuid4()
    result = RecurringBookingSeriesResult(
        id=uuid4(),
        user_id=uuid4(),
        first_occurrence_date=date(2026, 1, 13),
        last_occurrence_date=date(2026, 2, 3),
        local_start_time=time(10, 0),
        local_end_time=time(12, 0),
        status="pending_payment",
        payment_hold_expires_at=expires_at,
        quoted_amount=Decimal("400"),
        currency="CAD",
        occurrence_count=1,
        occurrences=[
            RecurringBookingOccurrenceResult(
                id=occurrence_id,
                start_at=datetime(2026, 1, 13, 15, 0, tzinfo=timezone.utc),
                end_at=datetime(2026, 1, 13, 17, 0, tzinfo=timezone.utc),
                status="cancelled",
                quoted_amount=Decimal("100"),
                currency="CAD",
                facility_ids=[],
            )
        ],
    )
    dumped = recurring_booking_series_to_member_api(result).model_dump(by_alias=True)
    assert dumped["status"] == "pending_payment"
    assert dumped["paymentHoldExpiresAt"] == expires_at
    assert dumped["quotedAmount"] == Decimal("400")
    assert dumped["occurrences"][0]["id"] == str(occurrence_id)
    assert dumped["occurrences"][0]["status"] == "cancelled"


def test_create_room_blackout_to_command_keeps_confirm_occurrence_ids():
    occurrence_id = uuid4()
    command = create_room_blackout_to_command(
        AdminRoomBlackoutCreate(
            name="Maintenance",
            reason="HVAC work",
            kind="one_off",
            blackout_date=date(2026, 7, 21),
            start_time=time(9, 0),
            end_time=time(12, 0),
            confirm_occurrence_ids=[occurrence_id],
        )
    )
    assert command.confirm_occurrence_ids == [occurrence_id]


def test_blackout_impact_to_api_exposes_series_and_ministry():
    occurrence_id = uuid4()
    series_id = uuid4()
    ministry_id = uuid4()
    start_at = datetime(2026, 7, 21, 13, 0, tzinfo=timezone.utc)
    result = BlackoutImpactResult(
        confirmation_required=True,
        items=[
            BlackoutImpactOccurrenceResult(
                id=occurrence_id,
                series_id=series_id,
                start_at=start_at,
                end_at=datetime(2026, 7, 21, 15, 0, tzinfo=timezone.utc),
                status="confirmed",
                facility_ids=[uuid4()],
                ministry_id=ministry_id,
            )
        ],
    )
    dumped = blackout_impact_to_api(result).model_dump(by_alias=True)
    assert dumped["confirmationRequired"] is True
    assert dumped["items"][0]["id"] == str(occurrence_id)
    assert dumped["items"][0]["seriesId"] == series_id
    assert dumped["items"][0]["ministryId"] == ministry_id
    assert dumped["items"][0]["status"] == "confirmed"


def test_member_booking_list_item_exposes_series_id():
    series_id = uuid4()
    result = MemberBrowseBookingResult(
        id=uuid4(),
        user_id=uuid4(),
        booking_type="recurring",
        series_id=series_id,
        start_at=datetime(2026, 9, 24, 13, 0, tzinfo=timezone.utc),
        end_at=datetime(2026, 9, 24, 14, 30, tzinfo=timezone.utc),
        status="confirmed",
    )
    dumped = member_browse_booking_to_api(result).model_dump(by_alias=True)
    assert dumped["seriesId"] == series_id
    assert dumped["bookingType"] == "recurring"


def test_member_booking_list_item_one_time_series_id_is_null():
    result = MemberBrowseBookingResult(
        id=uuid4(),
        user_id=uuid4(),
        booking_type="one_time",
        start_at=datetime(2026, 9, 18, 15, 0, tzinfo=timezone.utc),
        end_at=datetime(2026, 9, 18, 16, 30, tzinfo=timezone.utc),
        status="confirmed",
    )
    dumped = member_browse_booking_to_api(result).model_dump(by_alias=True)
    assert dumped["seriesId"] is None
    assert dumped["bookingType"] == "one_time"


def test_admin_booking_pages_and_range_expose_series_id_for_occurrence():
    series_id = uuid4()
    item = BookingListItemResult(
        id=uuid4(),
        user_id=uuid4(),
        booking_type="recurring",
        series_id=series_id,
        start_at=datetime(2026, 9, 24, 13, 0, tzinfo=timezone.utc),
        end_at=datetime(2026, 9, 24, 14, 30, tzinfo=timezone.utc),
        status="confirmed",
    )
    pages = booking_page_to_api(BookingPageResult(page=0, page_size=20, total=1, items=[item])).model_dump(by_alias=True)
    ranged = booking_range_to_api(BookingRangeResult(items=[item])).model_dump(by_alias=True)
    assert pages["items"][0]["seriesId"] == series_id
    assert pages["items"][0]["bookingType"] == "recurring"
    assert ranged["items"][0]["seriesId"] == series_id
    assert ranged["items"][0]["bookingType"] == "recurring"


def test_admin_booking_pages_and_range_one_time_series_id_is_null():
    item = BookingListItemResult(
        id=uuid4(),
        user_id=uuid4(),
        booking_type="one_time",
        start_at=datetime(2026, 9, 18, 15, 0, tzinfo=timezone.utc),
        end_at=datetime(2026, 9, 18, 16, 30, tzinfo=timezone.utc),
        status="confirmed",
    )
    pages = booking_page_to_api(BookingPageResult(page=0, page_size=20, total=1, items=[item])).model_dump(by_alias=True)
    ranged = booking_range_to_api(BookingRangeResult(items=[item])).model_dump(by_alias=True)
    assert pages["items"][0]["seriesId"] is None
    assert pages["items"][0]["bookingType"] == "one_time"
    assert ranged["items"][0]["seriesId"] is None
    assert ranged["items"][0]["bookingType"] == "one_time"


def test_admin_booking_detail_exposes_series_id_for_occurrence():
    series_id = uuid4()
    result = BookingDetailResult(
        id=uuid4(),
        user_id=uuid4(),
        booking_type="recurring",
        series_id=series_id,
        start_at=datetime(2026, 9, 24, 13, 0, tzinfo=timezone.utc),
        end_at=datetime(2026, 9, 24, 14, 30, tzinfo=timezone.utc),
        status="confirmed",
    )
    dumped = booking_detail_to_api(result).model_dump(by_alias=True)
    assert dumped["seriesId"] == series_id
    assert dumped["bookingType"] == "recurring"


def test_admin_booking_detail_one_time_series_id_is_null():
    result = BookingDetailResult(
        id=uuid4(),
        user_id=uuid4(),
        booking_type="one_time",
        start_at=datetime(2026, 9, 18, 15, 0, tzinfo=timezone.utc),
        end_at=datetime(2026, 9, 18, 16, 30, tzinfo=timezone.utc),
        status="confirmed",
    )
    dumped = booking_detail_to_api(result).model_dump(by_alias=True)
    assert dumped["seriesId"] is None
    assert dumped["bookingType"] == "one_time"


def test_admin_booking_pages_and_range_expose_ministry_for_church_activity():
    ministry_id = uuid4()
    item = BookingListItemResult(
        id=uuid4(),
        user_id=uuid4(),
        booking_type="recurring",
        ministry_id=ministry_id,
        ministry_name="Youth Fellowship",
        start_at=datetime(2026, 9, 24, 13, 0, tzinfo=timezone.utc),
        end_at=datetime(2026, 9, 24, 14, 30, tzinfo=timezone.utc),
        status="confirmed",
    )
    pages = booking_page_to_api(BookingPageResult(page=0, page_size=20, total=1, items=[item])).model_dump(by_alias=True)
    ranged = booking_range_to_api(BookingRangeResult(items=[item])).model_dump(by_alias=True)
    assert pages["items"][0]["ministryId"] == ministry_id
    assert pages["items"][0]["ministryName"] == "Youth Fellowship"
    assert ranged["items"][0]["ministryId"] == ministry_id
    assert ranged["items"][0]["ministryName"] == "Youth Fellowship"


def test_admin_booking_pages_and_range_personal_rental_ministry_is_null():
    item = BookingListItemResult(
        id=uuid4(),
        user_id=uuid4(),
        booking_type="one_time",
        start_at=datetime(2026, 9, 18, 15, 0, tzinfo=timezone.utc),
        end_at=datetime(2026, 9, 18, 16, 30, tzinfo=timezone.utc),
        status="confirmed",
    )
    pages = booking_page_to_api(BookingPageResult(page=0, page_size=20, total=1, items=[item])).model_dump(by_alias=True)
    ranged = booking_range_to_api(BookingRangeResult(items=[item])).model_dump(by_alias=True)
    assert pages["items"][0]["ministryId"] is None
    assert pages["items"][0]["ministryName"] is None
    assert ranged["items"][0]["ministryId"] is None
    assert ranged["items"][0]["ministryName"] is None


def test_admin_booking_pages_and_range_ministry_name_null_when_no_translation():
    ministry_id = uuid4()
    item = BookingListItemResult(
        id=uuid4(),
        user_id=uuid4(),
        booking_type="one_time",
        ministry_id=ministry_id,
        start_at=datetime(2026, 9, 18, 15, 0, tzinfo=timezone.utc),
        end_at=datetime(2026, 9, 18, 16, 30, tzinfo=timezone.utc),
        status="confirmed",
    )
    pages = booking_page_to_api(BookingPageResult(page=0, page_size=20, total=1, items=[item])).model_dump(by_alias=True)
    ranged = booking_range_to_api(BookingRangeResult(items=[item])).model_dump(by_alias=True)
    assert pages["items"][0]["ministryId"] == ministry_id
    assert pages["items"][0]["ministryName"] is None
    assert ranged["items"][0]["ministryId"] == ministry_id
    assert ranged["items"][0]["ministryName"] is None


def test_admin_booking_detail_exposes_ministry_for_church_activity():
    ministry_id = uuid4()
    result = BookingDetailResult(
        id=uuid4(),
        user_id=uuid4(),
        booking_type="recurring",
        ministry_id=ministry_id,
        ministry_name="Youth Fellowship",
        start_at=datetime(2026, 9, 24, 13, 0, tzinfo=timezone.utc),
        end_at=datetime(2026, 9, 24, 14, 30, tzinfo=timezone.utc),
        status="confirmed",
    )
    dumped = booking_detail_to_api(result).model_dump(by_alias=True)
    assert dumped["ministryId"] == ministry_id
    assert dumped["ministryName"] == "Youth Fellowship"


def test_admin_booking_detail_personal_rental_ministry_is_null():
    result = BookingDetailResult(
        id=uuid4(),
        user_id=uuid4(),
        booking_type="one_time",
        start_at=datetime(2026, 9, 18, 15, 0, tzinfo=timezone.utc),
        end_at=datetime(2026, 9, 18, 16, 30, tzinfo=timezone.utc),
        status="confirmed",
    )
    dumped = booking_detail_to_api(result).model_dump(by_alias=True)
    assert dumped["ministryId"] is None
    assert dumped["ministryName"] is None


def test_admin_recurring_booking_series_detail_exposes_ministry_name():
    ministry_id = uuid4()
    result = RecurringBookingSeriesResult(
        id=uuid4(),
        user_id=uuid4(),
        ministry_id=ministry_id,
        ministry_name="Youth Fellowship",
        first_occurrence_date=date(2026, 1, 13),
        last_occurrence_date=date(2026, 2, 3),
        local_start_time=time(10, 0),
        local_end_time=time(12, 0),
        status="confirmed",
        quoted_amount=Decimal("400"),
        currency="CAD",
        occurrence_count=0,
    )
    dumped = recurring_booking_series_to_admin_api(result).model_dump(by_alias=True)
    assert dumped["ministryId"] == ministry_id
    assert dumped["ministryName"] == "Youth Fellowship"


def test_booking_list_query_selects_ministry_id_and_name():
    source = getsource(BookingRepository._list_query)
    assert "FacilityBooking.ministry_id" in source
    assert "_ministry_name_subquery" in source


def test_booking_detail_query_selects_ministry_name():
    source = getsource(BookingRepository.get_detail)
    assert "_ministry_name_subquery" in source


def test_series_get_by_id_selects_ministry_name():
    source = getsource(RecurringBookingRepository.get_by_id)
    assert "_ministry_name_subquery" in source
    assert "ministry_name" in source
