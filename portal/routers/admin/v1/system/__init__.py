"""
Admin system API router package.
"""
from portal.libs.depends import DEFAULT_RATE_LIMITERS
from portal.routers.auth_router import AuthRouter
from portal.routers.admin.v1.system.setting import router as setting_router

router = AuthRouter(
    dependencies=[*DEFAULT_RATE_LIMITERS],
    is_admin=True,
)
router.include_router(setting_router, prefix="/settings", tags=["System Setting"])
