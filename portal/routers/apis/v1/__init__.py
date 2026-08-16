"""
Member API router aggregate.
"""

from portal.routers.auth_router import AuthRouter

from .auth import router as auth_router
from .facility import router as facility_router
from .ministry import router as ministry_router
from .org import router as org_router

router = AuthRouter()
router.include_router(auth_router, prefix="/auth", tags=["Auth"])
router.include_router(org_router, prefix="/org", tags=["Org"])
router.include_router(ministry_router, prefix="/ministry", tags=["Ministry"])
router.include_router(facility_router, prefix="/facility", tags=["Facility"])
