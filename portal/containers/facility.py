"""
Facility bounded context DI container.
"""

from dependency_injector import containers, providers

from portal.application.facility.booking_service import BookingService
from portal.application.facility.member_service import MemberService
from portal.application.facility.override_log_service import OverrideLogService
from portal.application.facility.pricing_service import PricingService
from portal.application.facility.rental_catalog_service import RentalCatalogService
from portal.application.facility.rental_rate_service import RentalRateService
from portal.application.facility.room_service import RoomService
from portal.application.facility.room_slot_template_service import RoomSlotTemplateService
from portal.infrastructure.persistence.repositories.facility.booking_repository import BookingRepository
from portal.infrastructure.persistence.repositories.facility.member_repository import MemberRepository
from portal.infrastructure.persistence.repositories.facility.override_log_repository import OverrideLogRepository
from portal.infrastructure.persistence.repositories.facility.rental_repository import RentalRepository
from portal.infrastructure.persistence.repositories.facility.room_repository import RoomRepository
from portal.infrastructure.persistence.repositories.facility.room_slot_template_repository import (
    RoomSlotTemplateRepository,
)
from portal.infrastructure.persistence.repositories.org.ministry_repository import MinistryRepository


class FacilityContainer(containers.DeclarativeContainer):
    """Facility booking admin services and repositories."""

    core = providers.DependenciesContainer()

    room_repository = providers.Factory(
        RoomRepository,
        session=core.request_session,
    )
    room_slot_template_repository = providers.Factory(
        RoomSlotTemplateRepository,
        session=core.request_session,
    )
    rental_repository = providers.Factory(
        RentalRepository,
        session=core.request_session,
    )
    ministry_repository = providers.Factory(
        MinistryRepository,
        session=core.request_session,
    )
    booking_repository = providers.Factory(
        BookingRepository,
        session=core.request_session,
    )
    member_repository = providers.Factory(
        MemberRepository,
        session=core.request_session,
    )
    override_log_repository = providers.Factory(
        OverrideLogRepository,
        session=core.request_session,
    )

    room_service = providers.Factory(
        RoomService,
        room_repository=room_repository,
    )
    room_slot_template_service = providers.Factory(
        RoomSlotTemplateService,
        room_slot_template_repository=room_slot_template_repository,
        room_repository=room_repository,
    )
    rental_rate_service = providers.Factory(
        RentalRateService,
        rental_repository=rental_repository,
        room_repository=room_repository,
    )
    rental_catalog_service = providers.Factory(
        RentalCatalogService,
        rental_repository=rental_repository,
    )
    pricing_service = providers.Factory(
        PricingService,
        rental_repository=rental_repository,
        room_repository=room_repository,
    )
    booking_service = providers.Factory(
        BookingService,
        booking_repository=booking_repository,
        pricing_service=pricing_service,
        rental_repository=rental_repository,
        ministry_repository=ministry_repository,
    )
    member_service = providers.Factory(
        MemberService,
        member_repository=member_repository,
        ministry_repository=ministry_repository,
    )
    override_log_service = providers.Factory(
        OverrideLogService,
        override_log_repository=override_log_repository,
    )
