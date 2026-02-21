"""
Root router - Template
"""
from fastapi import APIRouter

from .apis.v1 import router as api_v1_router

router = APIRouter()
router.include_router(api_v1_router, prefix="/v1")


@router.get(
    path="/healthz",
    operation_id="healthz"
)
async def healthz():
    """
    Healthcheck endpoint
    :return:
    """
    return {"message": "ok"}
