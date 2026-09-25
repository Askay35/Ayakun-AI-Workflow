from fastapi import APIRouter
import api.v1.auth as auth_router
import api.v1.telegram as telegram_router
import api.v1.users as user_router
import api.v1.workflows as workflow_router
import api.v1.webhooks as webhook_router
import api.v1.billing as billing_router
import api.v1.admin as admin_router
import api.v1.admin_records as admin_records_router
import api.v1.referrals as referrals_router

router = APIRouter(prefix="/api/v1")
router.include_router(auth_router.router, prefix="/auth")
router.include_router(telegram_router.router, prefix="/telegram")
router.include_router(user_router.router, prefix="/users")
router.include_router(workflow_router.router, prefix="/workflows", tags=["workflows"])
router.include_router(webhook_router.router, prefix="/webhooks", tags=["webhooks"])
router.include_router(billing_router.router, prefix="/billing", tags=["billing"])
router.include_router(referrals_router.router, prefix="/referrals", tags=["referrals"])
router.include_router(admin_router.router, prefix="/admin", tags=["admin"])
router.include_router(admin_records_router.router, prefix="/admin", tags=["admin"])
