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

class ApiPaymentResponse(BaseModel):
    confirmation_url: str
    model_config = ConfigDict(from_attributes=True)

class WalletResponse(BaseModel):
    user_id: int
    balance: Decimal
    reserved: Decimal
    currency: str = "CRD"
    media_unlocked: bool = False
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
    request_id: str = Field(min_length=8, max_length=160)


class RuntimeSettingUpdate(BaseModel):
    value: str | int | float | bool
    request_id: str = Field(min_length=8, max_length=160)
