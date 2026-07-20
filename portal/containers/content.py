"""
Content bounded context DI container.
"""
from dependency_injector import containers, providers

from portal.application.content.file_service import FileService
from portal.infrastructure.cache.file_cache import FileCache
from portal.infrastructure.persistence.repositories.content.file_repository import FileRepository
from portal.infrastructure.storage.azure_blob_storage import AzureBlobStorage


class ContentContainer(containers.DeclarativeContainer):
    """Content file admin services and repositories."""

    core = providers.DependenciesContainer()
    rbac_audit_service = providers.Dependency()

    file_repository = providers.Factory(
        FileRepository,
        session=core.request_session,
    )
    file_cache = providers.Factory(
        FileCache,
        redis_client=core.redis_client,
    )
    file_storage = providers.Factory(AzureBlobStorage)
    file_service = providers.Factory(
        FileService,
        file_repository=file_repository,
        file_storage=file_storage,
        file_cache=file_cache,
        rbac_audit_service=rbac_audit_service,
    )
