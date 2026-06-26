"""
Ministry admin API router aggregate.
"""
from portal.routers.auth_router import AuthRouter
from .ministry import router as ministry_router
from .ministry_approval import router as ministry_approval_router

router = AuthRouter(is_admin=True)
router.include_router(ministry_router, prefix="/ministries", tags=["Ministry"])
router.include_router(ministry_approval_router, prefix="/approvals", tags=["Ministry Approval"])
