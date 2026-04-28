"""
Top level router for admin v1 API
"""
from fastapi import APIRouter

from portal.config import settings
from portal.route_classes import LogRoute
from portal.libs.depends import DEFAULT_RATE_LIMITERS
from .auth import router as auth_router
from .permission import router as permission_router
from .resource import router as resource_router
from .role import router as role_router
from .verb import router as verb_router


router = APIRouter(
    dependencies=[
        *DEFAULT_RATE_LIMITERS
    ],
    route_class=LogRoute
)
router.include_router(auth_router, prefix="/auth", tags=["Auth"])
router.include_router(permission_router, prefix="/permission", tags=["Permission"])
router.include_router(resource_router, prefix="/resource", tags=["Resource"])
router.include_router(role_router, prefix="/role", tags=["Role"])
router.include_router(verb_router, prefix="/verb", tags=["Verb"])
# router.include_router(user_router, prefix="/user", tags=["User"])
