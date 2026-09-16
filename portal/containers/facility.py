"""
Facility bounded context DI container.
"""

from dependency_injector import containers, providers

from portal.application.facility.availability_service import AvailabilityService
from portal.application.facility.booking_draft_service import BookingDraftService
from portal.application.facility.booking_service import BookingService
from portal.application.facility.override_log_service import OverrideLogService
from portal.application.facility.pricing_service import PricingService
from portal.application.facility.recurring_booking_service import RecurringBookingService
from portal.application.facility.recurring_override_mail_service import RecurringOverrideMailService
from portal.application.facility.rental_catalog_service import RentalCatalogService
from portal.application.facility.rental_rate_service import RentalRateService
from portal.application.facility.rental_rate_template_service import RentalRateTemplateService
from portal.application.facility.room_blackout_service import RoomBlackoutService
from portal.application.facility.room_service import RoomService
from portal.application.facility.room_slot_template_service import RoomSlotTemplateService
from portal.config import settings as app_settings
from portal.infrastructure.persistence.repositories.facility.booking_draft_repository import BookingDraftRepository
from portal.infrastructure.persistence.repositories.facility.booking_repository import BookingRepository
from portal.infrastructure.persistence.repositories.facility.override_log_repository import OverrideLogRepository
from portal.infrastructure.persistence.repositories.facility.recurring_booking_repository import RecurringBookingRepository
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
    user_read_service = providers.Dependency()
    user_repository = providers.Dependency()
    permission_repository = providers.Dependency()
    position_repository = providers.Dependency()

    room_repository = providers.Factory(RoomRepository, session=core.request_session)
    room_slot_template_repository = providers.Factory(RoomSlotTemplateRepository, session=core.request_session)
    room_blackout_repository = providers.Factory(RoomBlackoutRepository, session=core.request_session)
    rental_repository = providers.Factory(RentalRepository, session=core.request_session)
    ministry_repository = providers.Factory(MinistryRepository, session=core.request_session)
    booking_repository = providers.Factory(BookingRepository, session=core.request_session)
    recurring_booking_repository = providers.Factory(RecurringBookingRepository, session=core.request_session)
    booking_draft_repository = providers.Factory(BookingDraftRepository, session=core.request_session)
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
        ministry_repository=ministry_repository,
        room_blackout_repository=room_blackout_repository,
        setting_service=setting_service,
        booking_draft_repository=booking_draft_repository,
    )
    booking_draft_service = providers.Factory(
        BookingDraftService,
        booking_draft_repository=booking_draft_repository,
        booking_repository=booking_repository,
        room_blackout_repository=room_blackout_repository,
        pricing_service=pricing_service,
        setting_service=setting_service,
    )
    recurring_override_mail_service = providers.Factory(
        RecurringOverrideMailService,
        mail_send_port=core.graph_mail_provider,
        email_template_render_port=core.email_template_render_provider,
        user_repository=user_repository,
        permission_repository=permission_repository,
        position_repository=position_repository,
        room_repository=room_repository,
        facility_booking_base_url=app_settings.FACILITY_BOOKING_BASE_URL,
        enabled=app_settings.GRAPH_MAIL_SEND_ENABLED,
        override_recipients=app_settings.graph_mail_override_recipients(),
    )
    recurring_booking_service = providers.Factory(
        RecurringBookingService,
        series_repository=recurring_booking_repository,
        booking_repository=booking_repository,
        pricing_service=pricing_service,
        ministry_repository=ministry_repository,
        room_blackout_repository=room_blackout_repository,
        setting_service=setting_service,
        user_read_service=user_read_service,
        override_log_repository=override_log_repository,
        override_notifier=recurring_override_mail_service,
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
