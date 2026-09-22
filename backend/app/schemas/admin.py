import datetime
import uuid
from decimal import Decimal
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator

from models.workflow import RunStatus, WorkflowStatus
from schemas.billing import LedgerKind, PaymentStatus

T = TypeVar("T")


class AdminPage(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int


class AdminIdentityResponse(BaseModel):
    provider: str
    subject: str
    created_at: datetime.datetime
    model_config = ConfigDict(from_attributes=True)


class AdminLedgerEntryResponse(BaseModel):
    id: uuid.UUID
    kind: LedgerKind
    amount: Decimal
    reference: str | None = None
    metadata: dict = Field(default_factory=dict)
    created_at: datetime.datetime
    model_config = ConfigDict(from_attributes=True)

    @field_serializer("amount")
    def serialize_amount(self, value: Decimal) -> float:
        return float(value)


class AdminUserResponse(BaseModel):
    id: int
    name: str
    email: str | None
    chat_id: int | None
    email_verified: bool
    is_active: bool
    balance: Decimal = Decimal("0")
    reserved: Decimal = Decimal("0")
    identities: list[AdminIdentityResponse] = Field(default_factory=list)
    ledger: list[AdminLedgerEntryResponse] = Field(default_factory=list)
    created_at: datetime.datetime
    updated_at: datetime.datetime
    model_config = ConfigDict(from_attributes=True)

    @field_serializer("balance", "reserved")
    def serialize_credits(self, value: Decimal) -> float:
        return float(value)


class AdminUserUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=120)
    email: str | None = Field(None, max_length=320)
    chat_id: int | None = None
    email_verified: bool | None = None
    is_active: bool | None = None
    balance: Decimal | None = Field(None, ge=0)
    note: str | None = Field(None, max_length=300)
    grant_plan_id: int | None = None
    request_id: str = Field(min_length=8, max_length=160)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip().lower()
        if not cleaned:
            return None
        if "@" not in cleaned or "." not in cleaned.split("@")[-1]:
            raise ValueError("Укажите корректный email")
        return cleaned

    @field_validator("grant_plan_id", mode="before")
    @classmethod
    def empty_grant(cls, value: object) -> int | None:
        if value is None or value is False or value == "":
            return None
        try:
            plan_id = int(value)  # type: ignore[arg-type]
        except (TypeError, ValueError) as exc:
            raise ValueError("Выберите пакет") from exc
        return plan_id or None

    @field_validator("note")
    @classmethod
    def normalize_note(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class AdminPaymentResponse(BaseModel):
    id: uuid.UUID
    user_id: int
    user_name: str | None = None
    user_email: str | None = None
    plan_id: int | None
    plan_name: str | None = None
    plan_code: str | None = None
    credits: Decimal | None = None
    provider: str
    provider_payment_id: str | None
    amount: Decimal
    status: PaymentStatus
    created_at: datetime.datetime
    updated_at: datetime.datetime
    model_config = ConfigDict(from_attributes=True)

    @field_serializer("amount", "credits")
    def serialize_money(self, value: Decimal | None) -> float | None:
        return None if value is None else float(value)


class AdminPaymentUpdate(BaseModel):
    status: PaymentStatus | None = None
    amount: Decimal | None = Field(None, ge=0)
    plan_id: int | None = None
    request_id: str = Field(min_length=8, max_length=160)


class AdminWorkflowResponse(BaseModel):
    id: uuid.UUID
    owner_id: int
    owner_name: str | None = None
    owner_email: str | None = None
    name: str
    description: str | None
    status: WorkflowStatus
    schedule_cron: str | None
    schedule_timezone: str
    next_run_at: datetime.datetime | None
    estimated_run_cost: Decimal
    nodes_count: int = 0
    created_at: datetime.datetime
    updated_at: datetime.datetime
    model_config = ConfigDict(from_attributes=True)

    @field_serializer("estimated_run_cost")
    def serialize_cost(self, value: Decimal) -> float:
        return float(value)


class AdminWorkflowUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=160)
    description: str | None = Field(None, max_length=4000)
    status: WorkflowStatus | None = None
    schedule_cron: str | None = Field(None, max_length=100)
    schedule_timezone: str | None = Field(None, min_length=1, max_length=64)
    request_id: str = Field(min_length=8, max_length=160)


class AdminRunResponse(BaseModel):
    id: uuid.UUID
    workflow_id: uuid.UUID
    workflow_name: str | None = None
    workflow_version_id: uuid.UUID
    owner_id: int
    owner_name: str | None = None
    owner_email: str | None = None
    status: RunStatus
    error: str | None
    cost: Decimal
    cancel_requested: bool
    started_at: datetime.datetime | None
    finished_at: datetime.datetime | None
    created_at: datetime.datetime
    model_config = ConfigDict(from_attributes=True)

    @field_serializer("cost")
    def serialize_cost(self, value: Decimal) -> float:
        return float(value)


class AdminRunUpdate(BaseModel):
    status: RunStatus | None = None
    error: str | None = Field(None, max_length=8000)
    cancel_requested: bool | None = None
    request_id: str = Field(min_length=8, max_length=160)
