"""
Content admin API router aggregate.
"""

from portal.routers.auth_router import AuthRouter

from .file import router as file_router
from .legal_document import router as legal_document_router

router = AuthRouter(is_admin=True)
router.include_router(file_router, prefix="/file", tags=["Content File"])
router.include_router(legal_document_router, prefix="/legal-document", tags=["Content Legal Document"])
