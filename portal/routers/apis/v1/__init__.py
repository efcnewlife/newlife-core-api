"""
Top level router for v1 API - Template: minimal placeholder
"""
from fastapi import APIRouter

from portal.config import settings
from portal.route_classes import LogRoute
from portal.libs.depends import DEFAULT_RATE_LIMITERS

router = APIRouter(
    dependencies=[
        *DEFAULT_RATE_LIMITERS
    ],
    route_class=LogRoute
)
# Add your API routes here, e.g.:
# router.include_router(auth_router, prefix="/auth", tags=["Auth"])
# router.include_router(user_router, prefix="/user", tags=["User"])
