"""
Facility rental rate application service.
"""
import uuid
from typing import Any, Optional
from uuid import UUID

from portal.application.facility.commands import (
    CreateRentalRateCommand,
    DeleteCommand,
    PagesQueryCommand,
    UpdateRentalRateCommand,
)
from portal.application.facility.results import CreateIdResult, RentalRateListResult, RentalRatePageResult, RentalRateResult
from portal.domain.facility.constants import RentalRateBillingUnit
from portal.exceptions.responses import ApiBaseException, BadRequestException, ConflictErrorException, NotFoundException
from portal.infrastructure.persistence.repositories.facility.rental_repository import RentalRepository
from portal.infrastructure.persistence.repositories.facility.room_repository import RoomRepository
from portal.libs.contexts.request_context import RequestContext, get_request_context
from portal.libs.logger import logger
from portal.libs.tracing.distributed_trace import distributed_trace


class RentalRateService:
    """Admin rental rate use cases."""

    def __init__(
        self,
        rental_repository: RentalRepository,
        room_repository: RoomRepository,
    ):
        self._repository = rental_repository
        self._room_repository = room_repository
        self._req_ctx: Optional[RequestContext] = get_request_context()

    def _resolved_locale_id(self) -> Optional[UUID]:
        if self._req_ctx and self._req_ctx.resolved_locale_id:
            return self._req_ctx.resolved_locale_id
        return None

    def _build_translation_payloads(
        self,
        command: CreateRentalRateCommand | UpdateRentalRateCommand,
    ) -> list[dict[str, Any]]:
        translation_payloads = command.translations or []
        return [
            dict(
                locale_id=item.locale_id,
                name=item.name,
                description=item.description,
                remark=item.remark,
            )
            for item in translation_payloads
        ]

    async def _validate_and_upsert_translations(self, rate_id: UUID, translation_payloads: list) -> None:
        if not translation_payloads:
            return
        locale_ids = [item["locale_id"] for item in translation_payloads]
        active_locale_ids = await self._repository.fetch_active_locale_ids(locale_ids)
        if len(active_locale_ids) != len(set(locale_ids)):
            raise BadRequestException(detail="Invalid or inactive locale_id in translations")
        rows = [dict(rental_rate_id=rate_id, **item) for item in translation_payloads]
        await self._repository.upsert_rate_translations(rows)

    @distributed_trace()
    async def get_rate_pages(
        self,
        command: PagesQueryCommand,
        facility_id: Optional[UUID] = None,
    ) -> RentalRatePageResult:
        items, count = await self._repository.fetch_rate_pages(command, self._resolved_locale_id(), facility_id)
        return RentalRatePageResult(page=command.page, page_size=command.page_size, total=count, items=items)

    @distributed_trace()
    async def get_rate_list(self, facility_id: Optional[UUID] = None) -> RentalRateListResult:
        items = await self._repository.list_rates(facility_id, self._resolved_locale_id())
        return RentalRateListResult(items=items)

    @distributed_trace()
    async def get_rate_by_id(
        self,
        rate_id: UUID,
        all_locales: bool = False,
    ) -> Optional[RentalRateResult]:
        return await self._repository.get_rate_by_id(
            rate_id,
            self._resolved_locale_id(),
            all_locales=all_locales,
        )

    @distributed_trace()
    async def create_rate(self, command: CreateRentalRateCommand) -> CreateIdResult:
        if not await self._room_repository.exists_by_id(command.facility_id):
            raise NotFoundException(detail=f"Room {command.facility_id} not found")
        billing_unit = command.billing_unit.value if hasattr(command.billing_unit, "value") else command.billing_unit
        if not billing_unit:
            billing_unit = RentalRateBillingUnit.HOURLY.value
        rate_id = uuid.uuid4()
        try:
            payload = {
                "id": rate_id,
                "facility_id": command.facility_id,
                "billing_unit": billing_unit,
                "unit_amount": command.unit_amount,
                "currency": command.currency,
                "is_default": command.is_default,
                "is_active": command.is_active,
                "effective_from": command.effective_from,
                "effective_to": command.effective_to,
            }
            if command.sequence is not None:
                payload["sequence"] = command.sequence
            await self._repository.insert_rate(payload)
            await self._validate_and_upsert_translations(rate_id, self._build_translation_payloads(command))
        except ApiBaseException:
            raise
        except Exception as error:
            if self._repository.is_unique_violation(error):
                raise ConflictErrorException(detail="Rental rate already exists for facility/unit/effective date")
            logger.exception(error)
            raise ApiBaseException(status_code=500, detail="Internal Server Error", debug_detail=str(error))
        return CreateIdResult(id=rate_id)

    @distributed_trace()
    async def update_rate(self, rate_id: UUID, command: UpdateRentalRateCommand) -> None:
        existing = await self._repository.get_rate_by_id(rate_id, self._resolved_locale_id())
        if not existing:
            raise NotFoundException(detail=f"Rental rate {rate_id} not found")
        if not await self._room_repository.exists_by_id(command.facility_id):
            raise NotFoundException(detail=f"Room {command.facility_id} not found")
        billing_unit = command.billing_unit.value if hasattr(command.billing_unit, "value") else command.billing_unit
        affected = await self._repository.update_rate(
            rate_id,
            {
                "facility_id": command.facility_id,
                "billing_unit": billing_unit,
                "unit_amount": command.unit_amount,
                "currency": command.currency,
                "is_default": command.is_default,
                "is_active": command.is_active,
                "effective_from": command.effective_from,
                "effective_to": command.effective_to,
                **({"sequence": command.sequence} if command.sequence is not None else {}),
            },
        )
        if affected == 0:
            raise NotFoundException(detail=f"Rental rate {rate_id} not found")
        await self._validate_and_upsert_translations(rate_id, self._build_translation_payloads(command))

    @distributed_trace()
    async def delete_rate(self, rate_id: UUID, command: DeleteCommand) -> None:
        if not await self._repository.get_rate_by_id(rate_id, self._resolved_locale_id()):
            raise NotFoundException(detail=f"Rental rate {rate_id} not found")
        if command.permanent:
            await self._repository.delete_rate_hard(rate_id)
        else:
            await self._repository.delete_rate_soft(rate_id, command.reason)

    @distributed_trace()
    async def restore_rate(self, rate_id: UUID) -> None:
        await self._repository.restore_rate(rate_id)
