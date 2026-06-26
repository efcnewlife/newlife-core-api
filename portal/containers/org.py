"""
Organization bounded context DI container.
"""

from dependency_injector import containers, providers

from portal.application.org.member_person_service import MemberPersonService
from portal.application.org.ministry_approval_service import MinistryApprovalService
from portal.application.org.ministry_service import MinistryService
from portal.application.org.position_service import PositionService
from portal.infrastructure.persistence.repositories.member.person_repository import PersonRepository
from portal.infrastructure.persistence.repositories.org.ministry_repository import MinistryRepository
from portal.infrastructure.persistence.repositories.org.position_repository import PositionRepository


class OrgContainer(containers.DeclarativeContainer):
    """Org admin services and repositories."""

    core = providers.DependenciesContainer()

    ministry_repository = providers.Factory(
        MinistryRepository,
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
