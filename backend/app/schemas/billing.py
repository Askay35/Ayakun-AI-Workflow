import datetime
from typing import Literal
import uuid
from decimal import Decimal
from enum import Enum
from pydantic import BaseModel, ConfigDict, Field
from yookassa.payment import PaymentResponse

from models.billing import LedgerKind


class PaymentEvent(str, Enum):
    PENDING = "pending"
    WAITING_FOR_CAPTURE = "waiting_for_capture"
    SUCCEEDED = "succeeded"
    CANCELED = "canceled"

class YooKassaWebhook(BaseModel):
    event: PaymentEvent
    object: PaymentResponse
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
    currency: str
    model_config = ConfigDict(from_attributes=True)


class SubscriptionResponse(BaseModel):
    id: uuid.UUID
    user_id: int
    plan_id: int
    status: str
    starts_at: datetime.datetime
    ends_at: datetime.datetime | None
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
