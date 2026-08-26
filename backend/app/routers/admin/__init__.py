from fastapi import APIRouter, Depends

from ...auth.dependencies import require_admin
from . import overview, projects

router = APIRouter(prefix="/api/v1/admin", tags=["admin"], dependencies=[Depends(require_admin)])
router.include_router(overview.router)
router.include_router(projects.router)
