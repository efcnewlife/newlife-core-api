"""
Booking Discount Eligibility application service.
"""

from decimal import Decimal
from typing import Optional
from uuid import UUID

from portal.application.facility.commands import EvaluateDiscountEligibilityCommand
from portal.application.facility.results import DiscountEligibilityResult
from portal.domain.facility.constants import BookingType, RentalDiscountCode
from portal.domain.org.constants import MinistryStatus
from portal.exceptions.responses import ForbiddenException
from portal.infrastructure.persistence.repositories.facility.rental_repository import RentalRepository
from portal.infrastructure.persistence.repositories.org.ministry_repository import MinistryRepository
from portal.libs.contexts.user_context import UserContext, get_user_context
from portal.libs.tracing.distributed_trace import distributed_trace


def _no_discount() -> DiscountEligibilityResult:
    return DiscountEligibilityResult(discount_code=None, discount_percent=Decimal("0"))


class DiscountEligibilityService:
    """Resolve the one Booking Discount applicable to a proposed booking."""

    def __init__(self, rental_repository: RentalRepository, ministry_repository: MinistryRepository):
        self._rental_repository = rental_repository
        self._ministry_repository = ministry_repository
        self._user_ctx: Optional[UserContext] = get_user_context()

    @distributed_trace()
    async def evaluate(self, command: EvaluateDiscountEligibilityCommand) -> DiscountEligibilityResult:
        booker_id = self._resolve_booker_id(command.booker_id)
        if await self._is_qualifying_ministry_booking(command.ministry_id, booker_id):
            return await self._active_discount_for_code(RentalDiscountCode.MISSION_ALIGNED)
        if command.booking_type == BookingType.RECURRING:
            return await self._active_discount_for_code(RentalDiscountCode.RECURRING_WEEKLY_MONTHLY)
        return _no_discount()

    def _resolve_booker_id(self, booker_id: Optional[UUID]) -> UUID:
        if booker_id is not None:
            return booker_id
        user_id = self._user_ctx.user_id if self._user_ctx else None
        if user_id is None:
            raise ForbiddenException(detail="Authenticated user required for discount eligibility")
        return user_id

    async def _is_qualifying_ministry_booking(self, ministry_id: Optional[UUID], booker_id: UUID) -> bool:
        if ministry_id is None:
            return False
        status = await self._ministry_repository.get_status(ministry_id)
        if status != MinistryStatus.ACTIVE.value:
            return False
        return await self._ministry_repository.is_user_booking_member(ministry_id, booker_id)

    async def _active_discount_for_code(self, code: RentalDiscountCode) -> DiscountEligibilityResult:
        rules = await self._rental_repository.list_discount_rules()
        for rule in rules:
            if rule.code == code.value and rule.is_active:
                return DiscountEligibilityResult(discount_code=rule.code, discount_percent=Decimal(str(rule.percent_off)))
        return _no_discount()
