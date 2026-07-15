"""
Organization bounded context DI container.
"""

from dependency_injector import containers, providers

from portal.application.org.member_person_service import MemberPersonService
from portal.application.org.ministry_catalog_service import MinistryCatalogService
from portal.application.org.ministry_approval_service import MinistryApprovalService
from portal.application.org.ministry_service import MinistryService
from portal.application.org.position_service import PositionService
from portal.infrastructure.persistence.repositories.member.person_repository import PersonRepository
from portal.infrastructure.persistence.repositories.org.ministry_repository import MinistryRepository
from portal.infrastructure.persistence.repositories.org.ministry_type_repository import MinistryTypeRepository
from portal.infrastructure.persistence.repositories.org.position_repository import PositionRepository
from portal.infrastructure.persistence.repositories.org.target_audience_repository import TargetAudienceRepository


class OrgContainer(containers.DeclarativeContainer):
    """Org admin services and repositories."""

    core = providers.DependenciesContainer()

    ministry_repository = providers.Factory(
        MinistryRepository,
        session=core.request_session,
    )
    ministry_type_repository = providers.Factory(
        MinistryTypeRepository,
        session=core.request_session,
    )
    target_audience_repository = providers.Factory(
        TargetAudienceRepository,
        session=core.request_session,
    )
    position_repository = providers.Factory(
        PositionRepository,
        session=core.request_session,
    )
    person_repository = providers.Factory(
        PersonRepository,
        session=core.request_session,
    )

    ministry_service = providers.Factory(
        MinistryService,
        ministry_repository=ministry_repository,
        ministry_type_repository=ministry_type_repository,
        target_audience_repository=target_audience_repository,
    )
    ministry_catalog_service = providers.Factory(
        MinistryCatalogService,
        ministry_type_repository=ministry_type_repository,
        target_audience_repository=target_audience_repository,
    )
    ministry_approval_service = providers.Factory(
        MinistryApprovalService,
        ministry_repository=ministry_repository,
        ministry_service=ministry_service,
    )
    position_service = providers.Factory(
        PositionService,
        position_repository=position_repository,
    )
    member_person_service = providers.Factory(
        MemberPersonService,
        person_repository=person_repository,
    )
