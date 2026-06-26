"""
Org admin API router aggregate.
"""
from portal.routers.auth_router import AuthRouter
from .member import router as member_router
from .position import router as position_router

router = AuthRouter(is_admin=True)
router.include_router(position_router, prefix="/positions", tags=["Org Position"])
router.include_router(member_router, prefix="/members", tags=["Org Member"])
