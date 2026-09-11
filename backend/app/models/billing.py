import datetime
import enum
import uuid
from decimal import Decimal

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base
from models.user import utcnow


class LedgerKind(str, enum.Enum):
    credit = "credit"
    purchase = "purchase"
    reserve = "reserve"
    charge = "charge"
    settle = "settle"
    release = "release"
    refund = "refund"


class PaymentStatus(str, enum.Enum):
    pending = "pending"
    succeeded = "succeeded"
    cancelled = "cancelled"


class Plan(Base):
    __tablename__ = "plans"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(50), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    price: Mapped[Decimal] = mapped_column(Numeric(18, 0), default=0)
    currency: Mapped[str] = mapped_column(String(3), default="RUB")
    limits: Mapped[dict] = mapped_column(JSONB, default=dict)


class Subscription(Base):
    __tablename__ = "subscriptions"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("plans.id"))
    status: Mapped[str] = mapped_column(String(30), default="active")
    starts_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    ends_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Wallet(Base):
    __tablename__ = "wallets"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    balance: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=0)
    reserved: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=0)
    currency: Mapped[str] = mapped_column(String(3), default="CRD")
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class WalletLedger(Base):
    __tablename__ = "wallet_ledger"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    kind: Mapped[LedgerKind] = mapped_column(Enum(LedgerKind, name="ledger_kind"))
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    idempotency_key: Mapped[str] = mapped_column(String(160), unique=True)
    reference: Mapped[str | None] = mapped_column(String(160), nullable=True)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class UsageRecord(Base):
    __tablename__ = "usage_records"
    __table_args__ = (UniqueConstraint("user_id", "idempotency_key", name="uq_usage_user_key"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    workflow_run_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("workflow_runs.id"), nullable=True)
    units: Mapped[int] = mapped_column(Integer, default=0)
    cost: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    idempotency_key: Mapped[str] = mapped_column(String(160))
    request_id: Mapped[str | None] = mapped_column(String(160), nullable=True, index=True)
    provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    input_cache_hit_tokens: Mapped[int] = mapped_column(Integer, default=0)
    input_cache_miss_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    provider_cost_usd: Mapped[Decimal] = mapped_column(Numeric(18, 9), default=0)
    details: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class BillingReservation(Base):
    __tablename__ = "billing_reservations"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    workflow_run_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("workflow_runs.id"), nullable=True, index=True)
    request_id: Mapped[str] = mapped_column(String(160), unique=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    charged: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=0)
    released: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=0)
    status: Mapped[str] = mapped_column(String(20), default="active")
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    closed_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    @property
    def remaining(self) -> Decimal:
        return max(self.amount - self.charged - self.released, Decimal("0"))


class PricingRate(Base):
    __tablename__ = "pricing_rates"
    id: Mapped[int] = mapped_column(primary_key=True)
    provider: Mapped[str] = mapped_column(String(50))
    model: Mapped[str] = mapped_column(String(120))
    input_cache_hit_credits_per_1k: Mapped[Decimal] = mapped_column(Numeric(18, 9), default=0)
    input_cache_miss_credits_per_1k: Mapped[Decimal] = mapped_column(Numeric(18, 9), default=0)
    output_credits_per_1k: Mapped[Decimal] = mapped_column(Numeric(18, 9), default=0)
    search_credits: Mapped[Decimal] = mapped_column(Numeric(18, 9), default=0)
    provider_costs: Mapped[dict] = mapped_column(JSONB, default=dict)
    active: Mapped[bool] = mapped_column(default=True)
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    __table_args__ = (UniqueConstraint("provider", "model", name="uq_pricing_provider_model"),)


class RuntimeSetting(Base):
    __tablename__ = "runtime_settings"
    key: Mapped[str] = mapped_column(String(120), primary_key=True)
    value: Mapped[dict] = mapped_column(JSONB, default=dict)
    description: Mapped[str] = mapped_column(String(300), default="")
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class BillingAudit(Base):
    __tablename__ = "billing_audit"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    actor: Mapped[str] = mapped_column(String(160))
    action: Mapped[str] = mapped_column(String(80))
    entity_type: Mapped[str] = mapped_column(String(80))
    entity_id: Mapped[str] = mapped_column(String(160))
    before: Mapped[dict] = mapped_column(JSONB, default=dict)
    after: Mapped[dict] = mapped_column(JSONB, default=dict)
    request_id: Mapped[str] = mapped_column(String(160), unique=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Payment(Base):
    __tablename__ = "payments"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    plan_id: Mapped[int | None] = mapped_column(ForeignKey("plans.id"), nullable=True)
    provider: Mapped[str] = mapped_column(String(30), default="yookassa")
    provider_payment_id: Mapped[str | None] = mapped_column(String(100), unique=True, nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    currency: Mapped[str] = mapped_column(String(3), default="RUB")
    status: Mapped[PaymentStatus] = mapped_column(Enum(PaymentStatus, name="payment_status"), default=PaymentStatus.pending)
    idempotency_key: Mapped[str] = mapped_column(String(160), unique=True)
    confirmation_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
