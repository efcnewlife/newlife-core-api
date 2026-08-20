"""
Facility rental rate application service.
"""

import uuid
from typing import Optional
from uuid import UUID

from portal.application.facility.commands import CreateRentalRateCommand, DeleteCommand, PagesQueryCommand, UpdateRentalRateCommand
from portal.application.facility.results import CreateIdResult, RentalRateListResult, RentalRatePageResult, RentalRateResult
from portal.domain.facility.constants import FacilityErrorCode
from portal.exceptions.responses import ApiBaseException, BadRequestException, ConflictErrorException, NotFoundException
from portal.infrastructure.persistence.repositories.facility.rental_repository import RentalRepository
from portal.infrastructure.persistence.repositories.facility.room_repository import RoomRepository
from portal.libs.logger import logger
from portal.libs.tracing.distributed_trace import distributed_trace


class RentalRateService:
    """Admin rental rate binding use cases (price always from template)."""

    def __init__(self, rental_repository: RentalRepository, room_repository: RoomRepository):
        self._repository = rental_repository
        self._room_repository = room_repository

    async def _validate_template_for_bind(self, template_id: UUID) -> None:
        template = await self._repository.get_template_by_id(template_id)
        if not template:
            raise NotFoundException(
                detail=f"Rental rate template {template_id} not found",
                error_code=FacilityErrorCode.RENTAL_RATE_TEMPLATE_NOT_FOUND.value,
                context={"template_id": str(template_id)},
            )
        if not template.is_active:
            raise BadRequestException(detail="Cannot bind rates to an inactive rental rate template")

    async def _validate_facility(self, facility_id: UUID) -> None:
        if not await self._room_repository.exists_by_id(facility_id):
            raise NotFoundException(
                detail=f"Room {facility_id} not found", error_code=FacilityErrorCode.ROOM_NOT_FOUND.value, context={"room_id": str(facility_id)}
            )

    @distributed_trace()
    async def get_rate_pages(self, command: PagesQueryCommand, facility_id: Optional[UUID] = None) -> RentalRatePageResult:
        items, count = await self._repository.fetch_rate_pages(command, facility_id=facility_id)
        return RentalRatePageResult(page=command.page, page_size=command.page_size, total=count, items=items)

    @distributed_trace()
    async def get_rate_list(self, facility_id: Optional[UUID] = None) -> RentalRateListResult:
        items = await self._repository.list_rates(facility_id)
        return RentalRateListResult(items=items)

    @distributed_trace()
    async def get_rate_by_id(self, rate_id: UUID) -> Optional[RentalRateResult]:
        return await self._repository.get_rate_by_id(rate_id)

    @distributed_trace()
    async def create_rate(self, command: CreateRentalRateCommand) -> CreateIdResult:
        await self._validate_facility(command.facility_id)
        await self._validate_template_for_bind(command.template_id)
        rate_id = uuid.uuid4()
        try:
            await self._repository.insert_rate(
                {"id": rate_id, "facility_id": command.facility_id, "template_id": command.template_id, "is_active": command.is_active}
            )
        except ApiBaseException:
            raise
        except Exception as error:
            if self._repository.is_unique_violation(error):
                raise ConflictErrorException(
                    detail="Rental rate binding already exists for facility/template", error_code=FacilityErrorCode.RENTAL_RATE_EXISTS.value
                )
            logger.exception(error)
            raise ApiBaseException(status_code=500, detail="Internal Server Error", debug_detail=str(error))
        return CreateIdResult(id=rate_id)

    @distributed_trace()
    async def update_rate(self, rate_id: UUID, command: UpdateRentalRateCommand) -> None:
        existing = await self._repository.get_rate_by_id(rate_id)
        if not existing:
            raise NotFoundException(
                detail=f"Rental rate {rate_id} not found", error_code=FacilityErrorCode.RENTAL_RATE_NOT_FOUND.value, context={"rate_id": str(rate_id)}
            )
        await self._validate_facility(command.facility_id)
        await self._validate_template_for_bind(command.template_id)
        try:
            affected = await self._repository.update_rate(
                rate_id, {"facility_id": command.facility_id, "template_id": command.template_id, "is_active": command.is_active}
            )
        except Exception as error:
            if self._repository.is_unique_violation(error):
                raise ConflictErrorException(
                    detail="Rental rate binding already exists for facility/template", error_code=FacilityErrorCode.RENTAL_RATE_EXISTS.value
                )
            raise
        if affected == 0:
            raise NotFoundException(
                detail=f"Rental rate {rate_id} not found", error_code=FacilityErrorCode.RENTAL_RATE_NOT_FOUND.value, context={"rate_id": str(rate_id)}
            )

    @distributed_trace()
    async def delete_rate(self, rate_id: UUID, command: DeleteCommand) -> None:
        existing = await self._repository.get_rate_by_id(rate_id)
        if not existing:
            raise NotFoundException(
                detail=f"Rental rate {rate_id} not found", error_code=FacilityErrorCode.RENTAL_RATE_NOT_FOUND.value, context={"rate_id": str(rate_id)}
            )
        if command.permanent:
            await self._repository.delete_rate_hard(rate_id)
        else:
            await self._repository.delete_rate_soft(rate_id, command.reason)

    @distributed_trace()
    async def restore_rate(self, rate_id: UUID) -> None:
        await self._repository.restore_rate(rate_id)
