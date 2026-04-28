"""
Admin API routers (mounted under /admin on the public ASGI app).
"""

from portal.routers.auth_router import AuthRouter
from .v1 import router as admin_v1_router

router: AuthRouter = AuthRouter(is_admin=True)
router.include_router(admin_v1_router, prefix="/v1")
