"""
Top level router for admin v1 API
"""
from portal.libs.depends import DEFAULT_RATE_LIMITERS
from portal.routers.auth_router import AuthRouter
from .auth import router as auth_router
from .locale import router as locale_router
from .permission import router as permission_router
from .resource import router as resource_router
from .role import router as role_router
from .user import router as user_router
from .verb import router as verb_router

router = AuthRouter(
    dependencies=[
        *DEFAULT_RATE_LIMITERS
    ],
    is_admin=True
)
router.include_router(auth_router, prefix="/auth", tags=["Auth"])
router.include_router(locale_router, prefix="/locale", tags=["Locale"])
router.include_router(permission_router, prefix="/permission", tags=["Permission"])
router.include_router(resource_router, prefix="/resource", tags=["Resource"])
router.include_router(role_router, prefix="/role", tags=["Role"])
router.include_router(user_router, prefix="/user", tags=["User"])
router.include_router(verb_router, prefix="/verb", tags=["Verb"])
