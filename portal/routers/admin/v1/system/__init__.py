"""
Admin system API router package.
"""

from portal.routers.admin.v1.system.setting import router as setting_router
from portal.routers.auth_router import AuthRouter

router = AuthRouter(is_admin=True)
router.include_router(setting_router, prefix="/settings", tags=["System Setting"])
