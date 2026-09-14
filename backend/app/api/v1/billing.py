from fastapi import APIRouter, Depends, HTTPException, status
from starlette.responses import RedirectResponse

from deps.auth import CurrentUser
from deps.services import get_billing_service
from schemas.billing import (
    LedgerResponse,
    PaymentCreate,
    ApiPaymentResponse,
    PlanCheckout,
    PlanResponse,
    SubscriptionResponse,
    UsageResponse,
    WalletResponse,
    YooKassaWebhook,
)
from schemas.common import ApiResponse
from services.billing import BillingService

router = APIRouter()

@router.get("/plans", response_model=ApiResponse[list[PlanResponse]])
async def plans(service: BillingService = Depends(get_billing_service)):
    return ApiResponse(success=True, data=await service.plans())


@router.get("/wallet", response_model=ApiResponse[WalletResponse])
async def wallet(user: CurrentUser, service: BillingService = Depends(get_billing_service)):
    result = await service.ensure_initial_credit(user)
    return ApiResponse(success=True, data=result)


@router.get("/subscription", response_model=ApiResponse[SubscriptionResponse])
async def subscription(user: CurrentUser, service: BillingService = Depends(get_billing_service)):
    return ApiResponse(success=True, data=await service.subscription(user))


@router.get("/ledger", response_model=ApiResponse[list[LedgerResponse]])
async def ledger(user: CurrentUser, service: BillingService = Depends(get_billing_service)):
    return ApiResponse(success=True, data=await service.ledger(user))


@router.get("/usage", response_model=ApiResponse[list[UsageResponse]])
async def usage(user: CurrentUser, service: BillingService = Depends(get_billing_service)):
    return ApiResponse(success=True, data=await service.usage(user))

@router.post("/subscription/checkout", response_model=ApiResponse[ApiPaymentResponse], status_code=status.HTTP_201_CREATED)
async def subscription_checkout(
    data: PlanCheckout,
    user: CurrentUser,
    service: BillingService = Depends(get_billing_service),
):
    confirmation_url: str = await service.create_plan_checkout(
        user,
        data.plan_id,
    )
    return ApiResponse[ApiPaymentResponse](success=True, data=ApiPaymentResponse(confirmation_url=confirmation_url))


@router.post("/webhooks/yookassa", response_model=ApiResponse[None])
async def yookassa_webhook(data: YooKassaWebhook, service: BillingService = Depends(get_billing_service)):
    await service.process_payment_webhook(data.model_dump())
    return ApiResponse(success=True)
