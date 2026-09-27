from fastapi import APIRouter, Depends, Query, status

from deps.auth import CurrentUser
from deps.services import get_billing_service, get_workflow_service
from schemas.billing import (
    LedgerResponse,
    ApiPaymentResponse,
    PlanCheckout,
    PlanResponse,
    PromoCodeCheckResponse,
    StorageUsage,
    SubscriptionResponse,
    UsageResponse,
    WalletResponse,
    YooKassaWebhook,
)
from schemas.common import ApiResponse
from services.billing import BillingService
from services.billing.promo_codes import PromoCodeService
from services.billing.subscriptions import SubscriptionService, is_active, storage_limits
from services.workflow import WorkflowService

router = APIRouter()

@router.get("/plans", response_model=ApiResponse[list[PlanResponse]])
async def plans(service: BillingService = Depends(get_billing_service)):
    return ApiResponse(success=True, data=await service.plans())


@router.get("/wallet", response_model=ApiResponse[WalletResponse])
async def wallet(user: CurrentUser, service: BillingService = Depends(get_billing_service)):
    result = await service.ensure_initial_credit(user)
    return ApiResponse(success=True, data=WalletResponse.model_validate(result))


@router.get("/subscription", response_model=ApiResponse[SubscriptionResponse])
async def subscription(
    user: CurrentUser,
    service: BillingService = Depends(get_billing_service),
    workflows: WorkflowService = Depends(get_workflow_service),
):
    subscriptions = SubscriptionService(service.db)
    current = await subscriptions.get(user.id)
    plan = await subscriptions.current_plan(user.id)
    limits = storage_limits(plan)
    files, nbytes = await workflows.storage_usage(user)
    payload = SubscriptionResponse(
        plan=PlanResponse.model_validate(plan) if plan else None,
        status="none" if current is None else "active" if is_active(current) else "expired",
        started_at=current.started_at if current else None,
        expires_at=current.expires_at if current else None,
        files_purge_at=current.files_purge_at if current else None,
        storage=StorageUsage(files=files, max_files=limits.max_files, bytes=nbytes, max_bytes=limits.max_bytes),
    )
    return ApiResponse(success=True, data=payload)


@router.get("/ledger", response_model=ApiResponse[list[LedgerResponse]])
async def ledger(user: CurrentUser, service: BillingService = Depends(get_billing_service)):
    return ApiResponse(success=True, data=await service.ledger(user))


@router.get("/usage", response_model=ApiResponse[list[UsageResponse]])
async def usage(user: CurrentUser, service: BillingService = Depends(get_billing_service)):
    return ApiResponse(success=True, data=await service.usage(user))

@router.post("/checkout", response_model=ApiResponse[ApiPaymentResponse], status_code=status.HTTP_201_CREATED)
async def checkout(
    data: PlanCheckout,
    user: CurrentUser,
    service: BillingService = Depends(get_billing_service),
):
    confirmation_url: str = await service.create_plan_checkout(
        user,
        data.plan_id,
        data.idempotency_key,
        customer_email=data.customer_email,
        promo_code=data.promo_code,
    )
    return ApiResponse[ApiPaymentResponse](success=True, data=ApiPaymentResponse(confirmation_url=confirmation_url))


@router.get("/promo-codes/check", response_model=ApiResponse[PromoCodeCheckResponse])
async def check_promo_code(
    user: CurrentUser,
    code: str = Query(..., min_length=1, max_length=40),
    service: BillingService = Depends(get_billing_service),
):
    promo_service = PromoCodeService(service.db)
    promo = await promo_service.find(code)
    if promo is None or not promo.active:
        reason = "Промокод не найден или недействителен"
    elif promo_service.is_expired(promo):
        reason = "Срок действия промокода истёк"
    elif await promo_service.already_redeemed(promo.id, user.id):
        reason = "Этот промокод уже был использован на вашем аккаунте"
    else:
        return ApiResponse(success=True, data=PromoCodeCheckResponse(
            valid=True, code=promo.code, discount_percent=promo.discount_percent, plan_ids=promo.plan_ids
        ))
    return ApiResponse(success=True, data=PromoCodeCheckResponse(valid=False, code=code, reason=reason))


@router.post("/webhooks/yookassa", response_model=ApiResponse[None])
async def yookassa_webhook(data: YooKassaWebhook, service: BillingService = Depends(get_billing_service)):
    await service.process_payment_webhook(data.model_dump())
    return ApiResponse(success=True)
