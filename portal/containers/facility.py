"""
Facility bounded context DI container.
"""

from dependency_injector import containers, providers

from portal.application.facility.availability_service import AvailabilityService
from portal.application.facility.booking_service import BookingService
from portal.application.facility.override_log_service import OverrideLogService
from portal.application.facility.pricing_service import PricingService
from portal.application.facility.rental_catalog_service import RentalCatalogService
from portal.application.facility.rental_rate_service import RentalRateService
from portal.application.facility.rental_rate_template_service import RentalRateTemplateService
from portal.application.facility.room_blackout_service import RoomBlackoutService
from portal.application.facility.room_service import RoomService
from portal.application.facility.room_slot_template_service import RoomSlotTemplateService
from portal.infrastructure.persistence.repositories.facility.booking_repository import BookingRepository
from portal.infrastructure.persistence.repositories.facility.override_log_repository import OverrideLogRepository
from portal.infrastructure.persistence.repositories.facility.rental_repository import RentalRepository
from portal.infrastructure.persistence.repositories.facility.room_blackout_repository import RoomBlackoutRepository
from portal.infrastructure.persistence.repositories.facility.room_repository import RoomRepository
from portal.infrastructure.persistence.repositories.facility.room_slot_template_repository import RoomSlotTemplateRepository
from portal.infrastructure.persistence.repositories.org.ministry_repository import MinistryRepository


class FacilityContainer(containers.DeclarativeContainer):
    """Facility booking admin services and repositories."""

    core = providers.DependenciesContainer()
    setting_service = providers.Dependency()
    file_service = providers.Dependency()

    room_repository = providers.Factory(RoomRepository, session=core.request_session)
    room_slot_template_repository = providers.Factory(RoomSlotTemplateRepository, session=core.request_session)
    room_blackout_repository = providers.Factory(RoomBlackoutRepository, session=core.request_session)
    rental_repository = providers.Factory(RentalRepository, session=core.request_session)
    ministry_repository = providers.Factory(MinistryRepository, session=core.request_session)
    booking_repository = providers.Factory(BookingRepository, session=core.request_session)
    override_log_repository = providers.Factory(OverrideLogRepository, session=core.request_session)

    room_service = providers.Factory(RoomService, room_repository=room_repository, file_service=file_service)
    room_slot_template_service = providers.Factory(
        RoomSlotTemplateService, room_slot_template_repository=room_slot_template_repository, room_repository=room_repository
    )
    room_blackout_service = providers.Factory(RoomBlackoutService, room_blackout_repository=room_blackout_repository, room_repository=room_repository)
    rental_rate_template_service = providers.Factory(RentalRateTemplateService, rental_repository=rental_repository)
    rental_rate_service = providers.Factory(RentalRateService, rental_repository=rental_repository, room_repository=room_repository)
    rental_catalog_service = providers.Factory(RentalCatalogService, rental_repository=rental_repository)
    pricing_service = providers.Factory(PricingService, rental_repository=rental_repository, room_repository=room_repository)
    booking_service = providers.Factory(
        BookingService,
        booking_repository=booking_repository,
        pricing_service=pricing_service,
        rental_repository=rental_repository,
        ministry_repository=ministry_repository,
        room_blackout_repository=room_blackout_repository,
        setting_service=setting_service,
    )
    availability_service = providers.Factory(
        AvailabilityService,
        room_repository=room_repository,
        room_slot_template_repository=room_slot_template_repository,
        booking_repository=booking_repository,
        ministry_repository=ministry_repository,
        room_blackout_repository=room_blackout_repository,
        setting_service=setting_service,
        file_service=file_service,
    )
    override_log_service = providers.Factory(OverrideLogService, override_log_repository=override_log_repository)
