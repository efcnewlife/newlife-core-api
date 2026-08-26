"""
Admin Legal Document API routes.
"""

from typing import Annotated
from uuid import UUID

from dependency_injector.wiring import Provide, inject
from fastapi import Depends, Query, status

from portal.application.content.legal_document_service import LegalDocumentService
from portal.application.content.mappers import (
    legal_document_detail_to_api,
    legal_document_page_result_to_api,
    legal_document_pages_query_to_command,
    update_legal_document_to_command,
)
from portal.container import Container
from portal.libs.consts.permission import Permission
from portal.routers.auth_router import AuthRouter
from portal.serializers.admin.v1.legal_document import AdminLegalDocumentDetail, AdminLegalDocumentPages, AdminLegalDocumentQuery, AdminLegalDocumentUpdate

router: AuthRouter = AuthRouter(is_admin=True)


@router.get(path="/pages", status_code=status.HTTP_200_OK, response_model=AdminLegalDocumentPages, permissions=[Permission.CONTENT_LEGAL_DOCUMENT.read])
@inject
async def get_legal_document_pages(
    query_model: Annotated[AdminLegalDocumentQuery, Query()], legal_document_service: LegalDocumentService = Depends(Provide[Container.legal_document_service])
):
    result = await legal_document_service.get_legal_document_pages(command=legal_document_pages_query_to_command(query_model))
    return legal_document_page_result_to_api(result)


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
