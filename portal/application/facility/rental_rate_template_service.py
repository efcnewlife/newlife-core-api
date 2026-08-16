"""
Facility rental rate template application service.
"""

import json
import uuid
from typing import Optional
from uuid import UUID

from pydantic import ValidationError

from portal.application.facility.commands import CreateRentalRateTemplateCommand, DeleteCommand, PagesQueryCommand, UpdateRentalRateTemplateCommand
from portal.application.facility.results import CreateIdResult, RentalRateTemplateListResult, RentalRateTemplatePageResult, RentalRateTemplateResult
from portal.domain.facility.constants import RentalRateBillingUnit
from portal.domain.facility.rate_applicability import parse_applicability
from portal.exceptions.responses import ApiBaseException, BadRequestException, ConflictErrorException, NotFoundException
from portal.infrastructure.persistence.repositories.facility.rental_repository import RentalRepository
from portal.libs.logger import logger
from portal.libs.tracing.distributed_trace import distributed_trace


class RentalRateTemplateService:
    """Admin rental rate template use cases."""

    def __init__(self, rental_repository: RentalRepository):
        self._repository = rental_repository

    def _applicability_for_storage(self, raw) -> str | None:
        try:
            validated = parse_applicability(raw)
        except (ValidationError, ValueError) as error:
            raise BadRequestException(detail=f"Invalid applicability rule: {error}") from error
        if validated is None:
            return None
        return json.dumps(validated)

    def _billing_unit_value(self, billing_unit) -> str:
        if hasattr(billing_unit, "value"):
            return billing_unit.value
        return billing_unit or RentalRateBillingUnit.HOURLY.value

    @distributed_trace()
    async def get_template_pages(self, command: PagesQueryCommand) -> RentalRateTemplatePageResult:
        items, count = await self._repository.fetch_template_pages(command)
        return RentalRateTemplatePageResult(page=command.page, page_size=command.page_size, total=count, items=items)

    @distributed_trace()
    async def get_template_list(self) -> RentalRateTemplateListResult:
        items = await self._repository.list_templates(active_only=False)
        return RentalRateTemplateListResult(items=items)

    @distributed_trace()
    async def get_template_by_id(self, template_id: UUID) -> Optional[RentalRateTemplateResult]:
        return await self._repository.get_template_by_id(template_id)

    @distributed_trace()
    async def create_template(self, command: CreateRentalRateTemplateCommand) -> CreateIdResult:
        template_id = uuid.uuid4()
        try:
            await self._repository.insert_template(
                {
                    "id": template_id,
                    "name": command.name,
                    "billing_unit": self._billing_unit_value(command.billing_unit),
                    "applicability": self._applicability_for_storage(command.applicability),
                    "unit_amount": command.unit_amount,
                    "currency": command.currency or "CAD",
                    "is_default": command.is_default,
                    "is_active": command.is_active,
                }
            )
        except ApiBaseException:
            raise
        except Exception as error:
            if self._repository.is_unique_violation(error):
                raise ConflictErrorException(detail="Rental rate template name already exists")
            logger.exception(error)
            raise ApiBaseException(status_code=500, detail="Internal Server Error", debug_detail=str(error))
        return CreateIdResult(id=template_id)

    @distributed_trace()
    async def update_template(self, template_id: UUID, command: UpdateRentalRateTemplateCommand) -> None:
        existing = await self._repository.get_template_by_id(template_id)
        if not existing:
            raise NotFoundException(detail=f"Rental rate template {template_id} not found")
        try:
            affected = await self._repository.update_template(
                template_id,
                {
                    "name": command.name,
                    "billing_unit": self._billing_unit_value(command.billing_unit),
                    "applicability": self._applicability_for_storage(command.applicability),
                    "unit_amount": command.unit_amount,
                    "currency": command.currency or "CAD",
                    "is_default": command.is_default,
                    "is_active": command.is_active,
                },
            )
            if affected == 0:
                raise NotFoundException(detail=f"Rental rate template {template_id} not found")
        except ApiBaseException:
            raise
        except Exception as error:
            if self._repository.is_unique_violation(error):
                raise ConflictErrorException(detail="Rental rate template name already exists")
            raise

    @distributed_trace()
    async def delete_template(self, template_id: UUID, command: DeleteCommand) -> None:
        existing = await self._repository.get_template_by_id(template_id)
        if not existing:
            raise NotFoundException(detail=f"Rental rate template {template_id} not found")
        rate_count = await self._repository.count_rates_for_template(template_id)
        if rate_count > 0:
            raise BadRequestException(detail="Cannot delete rental rate template while rates still reference it")
        if command.permanent:
            raise BadRequestException(detail="Permanent delete is not supported for rental rate templates")
        await self._repository.delete_template_soft(template_id, command.reason)

    @distributed_trace()
    async def restore_template(self, template_id: UUID) -> None:
        await self._repository.restore_template(template_id)
