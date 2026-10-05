from fastapi import APIRouter, Depends

from ...auth.dependencies import require_admin
from . import (
    cost_gate_config,
    costs,
    credit_packs,
    earnings,
    model_config,
    overview,
    payments,
    projects,
    prompt_templates,
    tiers,
    users,
)

router = APIRouter(prefix="/api/v1/admin", tags=["admin"], dependencies=[Depends(require_admin)])
router.include_router(overview.router)
router.include_router(projects.router)
router.include_router(users.router)
router.include_router(costs.router)
router.include_router(model_config.router)
router.include_router(prompt_templates.router)
router.include_router(earnings.router)
router.include_router(cost_gate_config.router)
router.include_router(credit_packs.router)
router.include_router(payments.router)
router.include_router(tiers.router)
