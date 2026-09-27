import datetime
import uuid
from decimal import Decimal
from enum import Enum
from pydantic import BaseModel, ConfigDict, EmailStr, Field

class LedgerKind(str, Enum):
    credit = "credit"
    purchase = "purchase"
    reserve = "reserve"
    charge = "charge"
    settle = "settle"
    release = "release"
    refund = "refund"
    expire = "expire"
    referral = "referral"


class PaymentStatus(str, Enum):
    pending = "pending"
    succeeded = "succeeded"
    waiting_for_capture = "waiting_for_capture"
    canceled = "canceled"

class PaymentEvent(str, Enum):
    succeeded = "payment.succeeded"
    canceled = "payment.canceled"

class YooKassaPaymentObject(BaseModel):
    id: str
    status: PaymentStatus
    model_config = ConfigDict(extra="ignore")

class YooKassaWebhook(BaseModel):
    event: PaymentEvent
    object: YooKassaPaymentObject
    model_config = ConfigDict(from_attributes=True)


class PlanResponse(BaseModel):
    id: int
    code: str
    name: str
    price: Decimal
    currency: str
    limits: dict
    model_config = ConfigDict(from_attributes=True)

class StorageUsage(BaseModel):
    files: int
    max_files: int
    bytes: int
    max_bytes: int


class SubscriptionResponse(BaseModel):
    """Действующая подписка (пробный период — тоже подписка); без неё plan пуст."""

    plan: PlanResponse | None = None
    status: str = "none"
    started_at: datetime.datetime | None = None
    expires_at: datetime.datetime | None = None
    files_purge_at: datetime.datetime | None = None
    storage: StorageUsage


class ApiPaymentResponse(BaseModel):
    confirmation_url: str
    model_config = ConfigDict(from_attributes=True)

class WalletResponse(BaseModel):
    user_id: int
    balance: Decimal
    reserved: Decimal
    currency: str = "CRD"
    model_config = ConfigDict(from_attributes=True)

class LedgerResponse(BaseModel):
    id: uuid.UUID
    kind: LedgerKind
    amount: Decimal
    idempotency_key: str
    reference: str | None
    metadata_: dict = Field(default_factory=dict, validation_alias="metadata_", serialization_alias="metadata")
    created_at: datetime.datetime
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class UsageResponse(BaseModel):
    id: uuid.UUID
    workflow_run_id: uuid.UUID | None
    units: int
    cost: Decimal
    request_id: str | None
    provider: str | None
    model: str | None
    input_cache_hit_tokens: int
    input_cache_miss_tokens: int
    output_tokens: int
    provider_cost_usd: Decimal
    details: dict
    created_at: datetime.datetime
    model_config = ConfigDict(from_attributes=True)


class WalletOperation(BaseModel):
    amount: Decimal = Field(gt=0)
    idempotency_key: str = Field(min_length=8, max_length=160)
    reference: str | None = None


class SettleOperation(WalletOperation):
    units: int = Field(default=0, ge=0)
    workflow_run_id: uuid.UUID | None = None


class PaymentCreate(BaseModel):
    amount: Decimal = Field(gt=0)


class PlanCheckout(BaseModel):
    plan_id: int
    idempotency_key: str = Field(min_length=8, max_length=160)
    customer_email: EmailStr | None = None
    promo_code: str | None = Field(default=None, max_length=40)


class PromoCodeResponse(BaseModel):
    id: int
    code: str
    discount_percent: int
    plan_ids: list[int] | None
    expires_at: datetime.datetime | None
    active: bool
    usage_count: int = 0
    created_at: datetime.datetime
    model_config = ConfigDict(from_attributes=True)


class PromoCodeCheckResponse(BaseModel):
    valid: bool
    code: str
    discount_percent: int | None = None
    plan_ids: list[int] | None = None
    reason: str | None = None


class PromoCodeCreate(BaseModel):
    code: str = Field(min_length=3, max_length=40)
    discount_percent: int = Field(ge=1, le=100)
    plan_ids: list[int] | None = None
    expires_at: datetime.datetime | None = None
    active: bool = True
    request_id: str = Field(min_length=8, max_length=160)


class PromoCodeUpdate(BaseModel):
    discount_percent: int = Field(ge=1, le=100)
    plan_ids: list[int] | None = None
    expires_at: datetime.datetime | None = None
    active: bool = True
    request_id: str = Field(min_length=8, max_length=160)

class PricingRateResponse(BaseModel):
    id: int
    provider: str
    model: str
    input_cache_hit_credits_per_1k: Decimal
    input_cache_miss_credits_per_1k: Decimal
    output_credits_per_1k: Decimal
    search_credits: Decimal
    provider_costs: dict
    active: bool
    model_config = ConfigDict(from_attributes=True)


class PricingRateUpdate(BaseModel):
    search_credits: Decimal = Field(ge=0)
    active: bool = True
    request_id: str = Field(min_length=8, max_length=160)


class AdminPlanUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    price: Decimal = Field(ge=0)
    currency: str = Field(min_length=3, max_length=3)
    included_credits: Decimal = Field(ge=0)
    run_cap_credits: Decimal = Field(gt=0)
    max_files: int | None = Field(default=None, gt=0)
    max_storage_mb: int | None = Field(default=None, gt=0)
    request_id: str = Field(min_length=8, max_length=160)


class RuntimeSettingUpdate(BaseModel):
    value: str | int | float | bool
    request_id: str = Field(min_length=8, max_length=160)
