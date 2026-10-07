from fastapi import APIRouter

from .storage_router import router as storage_router
from .endpoint_router import router as endpoint_router
from .audit_router import router as audit_router

router = APIRouter(prefix='/api', tags=['api'])
router.include_router(storage_router)
router.include_router(endpoint_router)
router.include_router(audit_router)

