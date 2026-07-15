"""
Member API router aggregate.
"""
from portal.routers.auth_router import AuthRouter
from .ministry import router as ministry_router
from .org import router as org_router

router = AuthRouter()
router.include_router(org_router, prefix="/org", tags=["Org"])
router.include_router(ministry_router, prefix="/ministry", tags=["Ministry"])
