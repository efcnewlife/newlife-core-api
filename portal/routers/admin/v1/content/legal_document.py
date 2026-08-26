"""
Admin Legal Document API routes.
"""

from typing import Annotated
from uuid import UUID

from dependency_injector.wiring import Provide, inject
from fastapi import Depends, Query, status

from portal.application.content.legal_document_service import LegalDocumentService
from portal.application.content.mappers import (
    create_id_result_to_api,
    create_legal_document_to_command,
    delete_legal_document_to_command,
    legal_document_bulk_action_to_command,
    legal_document_detail_to_api,
    legal_document_page_result_to_api,
    legal_document_pages_query_to_command,
    update_legal_document_to_command,
)
from portal.container import Container
from portal.libs.consts.permission import Permission
from portal.routers.auth_router import AuthRouter
from portal.serializers.admin.v1.legal_document import (
    AdminLegalDocumentBulkAction,
    AdminLegalDocumentCreate,
    AdminLegalDocumentDetail,
    AdminLegalDocumentPages,
    AdminLegalDocumentQuery,
    AdminLegalDocumentUpdate,
)
from portal.serializers.mixins import DeleteBaseModel
from portal.serializers.mixins.model_mixins import UUIDBaseModel

router: AuthRouter = AuthRouter(is_admin=True)


@router.get(path="/pages", status_code=status.HTTP_200_OK, response_model=AdminLegalDocumentPages, permissions=[Permission.CONTENT_LEGAL_DOCUMENT.read])
@inject
async def get_legal_document_pages(
    query_model: Annotated[AdminLegalDocumentQuery, Query()], legal_document_service: LegalDocumentService = Depends(Provide[Container.legal_document_service])
):
    result = await legal_document_service.get_legal_document_pages(command=legal_document_pages_query_to_command(query_model))
    return legal_document_page_result_to_api(result)


@router.post(path="", status_code=status.HTTP_201_CREATED, response_model=UUIDBaseModel, permissions=[Permission.CONTENT_LEGAL_DOCUMENT.create])
@inject
async def create_legal_document(
    body: AdminLegalDocumentCreate, legal_document_service: LegalDocumentService = Depends(Provide[Container.legal_document_service])
):
    result = await legal_document_service.create_legal_document(command=create_legal_document_to_command(body))
    return create_id_result_to_api(result)


@router.put(path="/restore", status_code=status.HTTP_204_NO_CONTENT, permissions=[Permission.CONTENT_LEGAL_DOCUMENT.modify])
@inject
async def restore_legal_documents(
    body: AdminLegalDocumentBulkAction, legal_document_service: LegalDocumentService = Depends(Provide[Container.legal_document_service])
):
    await legal_document_service.restore_legal_documents(command=legal_document_bulk_action_to_command(body))


@router.get(
    path="/{document_id}", status_code=status.HTTP_200_OK, response_model=AdminLegalDocumentDetail, permissions=[Permission.CONTENT_LEGAL_DOCUMENT.read]
)
@inject
async def get_legal_document(document_id: UUID, legal_document_service: LegalDocumentService = Depends(Provide[Container.legal_document_service])):
    result = await legal_document_service.get_legal_document_by_id(document_id)
    return legal_document_detail_to_api(result)


@router.put(
    path="/{document_id}", status_code=status.HTTP_200_OK, response_model=AdminLegalDocumentDetail, permissions=[Permission.CONTENT_LEGAL_DOCUMENT.modify]
)
@inject
async def update_legal_document(
    document_id: UUID, body: AdminLegalDocumentUpdate, legal_document_service: LegalDocumentService = Depends(Provide[Container.legal_document_service])
):
    result = await legal_document_service.update_legal_document(document_id=document_id, command=update_legal_document_to_command(body))
    return legal_document_detail_to_api(result)


@router.delete(path="/{document_id}", status_code=status.HTTP_204_NO_CONTENT, permissions=[Permission.CONTENT_LEGAL_DOCUMENT.delete])
@inject
async def delete_legal_document(
    document_id: UUID, body: DeleteBaseModel, legal_document_service: LegalDocumentService = Depends(Provide[Container.legal_document_service])
):
    await legal_document_service.delete_legal_document(document_id=document_id, command=delete_legal_document_to_command(body))
