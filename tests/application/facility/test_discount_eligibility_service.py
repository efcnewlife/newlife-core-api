"""Booking Discount Eligibility application tests."""

from decimal import Decimal
from uuid import uuid4

import pytest

from portal.application.facility.commands import EvaluateDiscountEligibilityCommand
from portal.application.facility.discount_eligibility_service import DiscountEligibilityService
from portal.domain.facility.constants import BookingType, RentalDiscountCode
from portal.domain.org.constants import MinistryStatus
from portal.exceptions.responses import ForbiddenException
from tests.fixtures.facility.factories import make_discount_rule, make_ministry_detail
from tests.fixtures.facility.stubs import StubMinistryRepository, StubRentalRepository


def _user_ctx(monkeypatch, *, user_id):
    class UserCtx:
        pass

    ctx = UserCtx()
    ctx.user_id = user_id
    monkeypatch.setattr("portal.application.facility.discount_eligibility_service.get_user_context", lambda: ctx)
    return ctx


def _eligibility_service(*, discount_rules: list | None = None, ministry_stub: StubMinistryRepository | None = None) -> DiscountEligibilityService:
    if discount_rules is None:
        discount_rules = [
            make_discount_rule(RentalDiscountCode.MISSION_ALIGNED.value, Decimal("30")),
            make_discount_rule(RentalDiscountCode.RECURRING_WEEKLY_MONTHLY.value, Decimal("20")),
        ]
    return DiscountEligibilityService(StubRentalRepository(discount_rules=discount_rules), ministry_stub or StubMinistryRepository())


@pytest.mark.asyncio
async def test_one_time_without_ministry_receives_no_discount():
    booker_id = uuid4()
    service = _eligibility_service()
    result = await service.evaluate(EvaluateDiscountEligibilityCommand(booking_type=BookingType.ONE_TIME, booker_id=booker_id))
    assert result.discount_code is None
    assert result.discount_percent == Decimal("0")


@pytest.mark.asyncio
async def test_recurring_without_ministry_receives_recurring_discount():
    booker_id = uuid4()
    service = _eligibility_service()
    result = await service.evaluate(EvaluateDiscountEligibilityCommand(booking_type=BookingType.RECURRING, booker_id=booker_id))
    assert result.discount_code == RentalDiscountCode.RECURRING_WEEKLY_MONTHLY.value
    assert result.discount_percent == Decimal("20")


@pytest.mark.asyncio
async def test_qualifying_ministry_takes_precedence_over_recurring():
    booker_id = uuid4()
    ministry = make_ministry_detail()
    service = _eligibility_service(ministry_stub=StubMinistryRepository(ministry_by_id={ministry.id: ministry}, booking_member_user_ids={booker_id}))
    result = await service.evaluate(EvaluateDiscountEligibilityCommand(booking_type=BookingType.RECURRING, ministry_id=ministry.id, booker_id=booker_id))
    assert result.discount_code == RentalDiscountCode.MISSION_ALIGNED.value
    assert result.discount_percent == Decimal("30")


@pytest.mark.asyncio
async def test_inactive_ministry_falls_back_to_recurring_discount():
    booker_id = uuid4()
    ministry = make_ministry_detail()
    ministry = ministry.model_copy(update={"status": MinistryStatus.INACTIVE.value})
    service = _eligibility_service(ministry_stub=StubMinistryRepository(ministry_by_id={ministry.id: ministry}, booking_member_user_ids={booker_id}))
    result = await service.evaluate(EvaluateDiscountEligibilityCommand(booking_type=BookingType.RECURRING, ministry_id=ministry.id, booker_id=booker_id))
    assert result.discount_code == RentalDiscountCode.RECURRING_WEEKLY_MONTHLY.value
    assert result.discount_percent == Decimal("20")


@pytest.mark.asyncio
async def test_ineligible_booker_does_not_receive_ministry_discount():
    booker_id = uuid4()
    ministry = make_ministry_detail()
    service = _eligibility_service(ministry_stub=StubMinistryRepository(ministry_by_id={ministry.id: ministry}, booking_member_user_ids=set()))
    result = await service.evaluate(EvaluateDiscountEligibilityCommand(booking_type=BookingType.ONE_TIME, ministry_id=ministry.id, booker_id=booker_id))
    assert result.discount_code is None
    assert result.discount_percent == Decimal("0")


@pytest.mark.asyncio
async def test_inactive_or_absent_rule_yields_no_discount():
    booker_id = uuid4()
    ministry = make_ministry_detail()
    service = _eligibility_service(
        discount_rules=[
            make_discount_rule(RentalDiscountCode.MISSION_ALIGNED.value, Decimal("30"), is_active=False),
            make_discount_rule(RentalDiscountCode.RECURRING_WEEKLY_MONTHLY.value, Decimal("20"), is_active=False),
        ],
        ministry_stub=StubMinistryRepository(ministry_by_id={ministry.id: ministry}, booking_member_user_ids={booker_id}),
    )
    ministry_result = await service.evaluate(
        EvaluateDiscountEligibilityCommand(booking_type=BookingType.ONE_TIME, ministry_id=ministry.id, booker_id=booker_id)
    )
    recurring_result = await service.evaluate(EvaluateDiscountEligibilityCommand(booking_type=BookingType.RECURRING, booker_id=booker_id))
    assert ministry_result.discount_code is None
    assert ministry_result.discount_percent == Decimal("0")
    assert recurring_result.discount_code is None
    assert recurring_result.discount_percent == Decimal("0")


@pytest.mark.asyncio
async def test_inactive_ministry_rule_does_not_fall_through_to_recurring():
    booker_id = uuid4()
    ministry = make_ministry_detail()
    service = _eligibility_service(
        discount_rules=[
            make_discount_rule(RentalDiscountCode.MISSION_ALIGNED.value, Decimal("30"), is_active=False),
            make_discount_rule(RentalDiscountCode.RECURRING_WEEKLY_MONTHLY.value, Decimal("20")),
        ],
        ministry_stub=StubMinistryRepository(ministry_by_id={ministry.id: ministry}, booking_member_user_ids={booker_id}),
    )
    result = await service.evaluate(EvaluateDiscountEligibilityCommand(booking_type=BookingType.RECURRING, ministry_id=ministry.id, booker_id=booker_id))
    assert result.discount_code is None
    assert result.discount_percent == Decimal("0")
    booker_id = uuid4()
    service = _eligibility_service(discount_rules=[])
    result = await service.evaluate(EvaluateDiscountEligibilityCommand(booking_type=BookingType.RECURRING, booker_id=booker_id))
    assert result.discount_code is None
    assert result.discount_percent == Decimal("0")


@pytest.mark.asyncio
async def test_admin_on_behalf_uses_booker_not_operator(monkeypatch):
    operator_id = uuid4()
    booker_id = uuid4()
    ministry = make_ministry_detail()
    _user_ctx(monkeypatch, user_id=operator_id)
    service = _eligibility_service(ministry_stub=StubMinistryRepository(ministry_by_id={ministry.id: ministry}, booking_member_user_ids={booker_id}))
    result = await service.evaluate(EvaluateDiscountEligibilityCommand(booking_type=BookingType.ONE_TIME, ministry_id=ministry.id, booker_id=booker_id))
    assert result.discount_code == RentalDiscountCode.MISSION_ALIGNED.value
    assert result.discount_percent == Decimal("30")


@pytest.mark.asyncio
async def test_member_evaluate_uses_authenticated_booker(monkeypatch):
    booker_id = uuid4()
    ministry = make_ministry_detail()
    _user_ctx(monkeypatch, user_id=booker_id)
    service = _eligibility_service(ministry_stub=StubMinistryRepository(ministry_by_id={ministry.id: ministry}, booking_member_user_ids={booker_id}))
    result = await service.evaluate(EvaluateDiscountEligibilityCommand(booking_type=BookingType.ONE_TIME, ministry_id=ministry.id))
    assert result.discount_code == RentalDiscountCode.MISSION_ALIGNED.value
    assert result.discount_percent == Decimal("30")


@pytest.mark.asyncio
async def test_member_evaluate_requires_authenticated_booker(monkeypatch):
    monkeypatch.setattr("portal.application.facility.discount_eligibility_service.get_user_context", lambda: None)
    service = _eligibility_service()
    with pytest.raises(ForbiddenException, match="Authenticated user"):
        await service.evaluate(EvaluateDiscountEligibilityCommand(booking_type=BookingType.ONE_TIME))
