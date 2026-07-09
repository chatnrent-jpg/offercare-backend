from fastapi import APIRouter
from app.api.v1 import auth, matching, shifts, scale_ops, billing

api_v1_router = APIRouter()

api_v1_router.include_router(auth.router)
api_v1_router.include_router(shifts.router)
api_v1_router.include_router(matching.router)
api_v1_router.include_router(scale_ops.router, prefix="/scale", tags=["scale"])
api_v1_router.include_router(billing.router, prefix="/billing", tags=["billing"])

__all__ = ["api_v1_router"]
