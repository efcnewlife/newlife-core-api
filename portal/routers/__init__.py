"""
Top level router for routers
"""
from .admin import router as admin_api_router
from .apis import router as api_router

__all__ = [
    "admin_api_router",
    "api_router",
]
