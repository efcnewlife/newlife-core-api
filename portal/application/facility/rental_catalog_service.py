"""
Facility rental catalog application service (discounts, surcharges).
"""

import uuid
from uuid import UUID

from portal.application.facility.commands import (
    CreateDiscountRuleCommand,
    CreateSurchargeCommand,
    DeleteCommand,
    UpdateDiscountRuleCommand,
    UpdateSurchargeCommand,
)
from portal.application.facility.results import CreateIdResult, DiscountRuleListResult, DiscountRuleResult, SurchargeListResult, SurchargeResult
from portal.exceptions.responses import ApiBaseException, ConflictErrorException, NotFoundException
from portal.infrastructure.persistence.repositories.facility.rental_repository import RentalRepository
from portal.libs.tracing.distributed_trace import distributed_trace


class RentalCatalogService:
    """Admin rental catalog use cases."""

    def __init__(self, rental_repository: RentalRepository):
        self._repository = rental_repository

    @distributed_trace()
    async def list_discount_rules(self) -> DiscountRuleListResult:
        return DiscountRuleListResult(items=await self._repository.list_discount_rules())

    @distributed_trace()
    async def get_discount_rule(self, rule_id: UUID) -> DiscountRuleResult:
        rule = await self._repository.get_discount_rule_by_id(rule_id)
        if not rule:
            raise NotFoundException(detail=f"Discount rule {rule_id} not found")
        return rule

    @distributed_trace()
    async def create_discount_rule(self, command: CreateDiscountRuleCommand) -> CreateIdResult:
        rule_id = uuid.uuid4()
        try:
            await self._repository.insert_discount_rule(
                {"id": rule_id, "code": command.code, "percent_off": command.percent_off, "is_active": command.is_active, "description": command.description}
            )
        except ApiBaseException:
            raise
        except Exception as error:
            if self._repository.is_unique_violation(error):
                raise ConflictErrorException(detail="Discount rule code already exists")
            raise ApiBaseException(status_code=500, detail="Internal Server Error", debug_detail=str(error))
        return CreateIdResult(id=rule_id)

    @distributed_trace()
    async def update_discount_rule(self, rule_id: UUID, command: UpdateDiscountRuleCommand) -> None:
        affected = await self._repository.update_discount_rule(
            rule_id, {"code": command.code, "percent_off": command.percent_off, "is_active": command.is_active, "description": command.description}
        )
        if affected == 0:
            raise NotFoundException(detail=f"Discount rule {rule_id} not found")

    @distributed_trace()
    async def delete_discount_rule(self, rule_id: UUID, command: DeleteCommand) -> None:
        if not await self._repository.get_discount_rule_by_id(rule_id):
            raise NotFoundException(detail=f"Discount rule {rule_id} not found")
        await self._repository.delete_discount_rule_soft(rule_id, command.reason)

    @distributed_trace()
    async def list_surcharges(self) -> SurchargeListResult:
        return SurchargeListResult(items=await self._repository.list_surcharges())

    @distributed_trace()
    async def get_surcharge(self, surcharge_id: UUID) -> SurchargeResult:
        surcharge = await self._repository.get_surcharge_by_id(surcharge_id)
        if not surcharge:
            raise NotFoundException(detail=f"Surcharge {surcharge_id} not found")
        return surcharge

    @distributed_trace()
    async def create_surcharge(self, command: CreateSurchargeCommand) -> CreateIdResult:
        surcharge_id = uuid.uuid4()
        try:
            await self._repository.insert_surcharge(
                {
                    "id": surcharge_id,
                    "code": command.code,
                    "charge_type": command.charge_type,
                    "unit_amount": command.unit_amount,
                    "currency": command.currency,
                    "is_active": command.is_active,
                    "applies_to_booking_type": command.applies_to_booking_type,
                    "remark": command.remark,
                }
            )
        except ApiBaseException:
            raise
        except Exception as error:
            if self._repository.is_unique_violation(error):
                raise ConflictErrorException(detail="Surcharge code already exists")
            raise ApiBaseException(status_code=500, detail="Internal Server Error", debug_detail=str(error))
        return CreateIdResult(id=surcharge_id)

    @distributed_trace()
    async def update_surcharge(self, surcharge_id: UUID, command: UpdateSurchargeCommand) -> None:
        affected = await self._repository.update_surcharge(
            surcharge_id,
            {
                "code": command.code,
                "charge_type": command.charge_type,
                "unit_amount": command.unit_amount,
                "currency": command.currency,
                "is_active": command.is_active,
                "applies_to_booking_type": command.applies_to_booking_type,
                "remark": command.remark,
            },
        )
        if affected == 0:
            raise NotFoundException(detail=f"Surcharge {surcharge_id} not found")

    @distributed_trace()
    async def delete_surcharge(self, surcharge_id: UUID, command: DeleteCommand) -> None:
        if not await self._repository.get_surcharge_by_id(surcharge_id):
            raise NotFoundException(detail=f"Surcharge {surcharge_id} not found")
        await self._repository.delete_surcharge_soft(surcharge_id, command.reason)
