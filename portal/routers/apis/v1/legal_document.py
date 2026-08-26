"""
Member public Legal Document API routes.
"""

from dependency_injector.wiring import Provide, inject
from fastapi import Depends, status

from portal.application.content.legal_document_service import LegalDocumentService
from portal.application.content.mappers import legal_document_public_result_to_api
from portal.container import Container
from portal.routers.auth_router import AuthRouter
from portal.serializers.apis.v1.legal_document import MemberLegalDocumentPublic

router: AuthRouter = AuthRouter()


@router.get(
    path="/{product}/{kind}", status_code=status.HTTP_200_OK, response_model=MemberLegalDocumentPublic, response_model_by_alias=True, require_auth=False
)
@inject
async def get_public_legal_document(product: str, kind: str, legal_document_service: LegalDocumentService = Depends(Provide[Container.legal_document_service])):
    result = await legal_document_service.get_public_legal_document(product=product, kind=kind)
    return legal_document_public_result_to_api(result)
