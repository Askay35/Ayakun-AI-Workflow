from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from models.billing import Payment, PaymentStatus, Plan, Wallet, WalletLedger
from models.user import User  # noqa: F401  — needed so Payment.user relationship can configure
from schemas.billing import LedgerKind, WalletResponse
from services.billing import BillingService
from services.providers import YooKassaProvider


class FakeTransaction:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class FakeDB:
    def __init__(self) -> None:
        self.plans: dict[int, Plan] = {}
        self.payment_by_key: Payment | None = None
        self.payment_by_provider: Payment | None = None
        self.wallet: Wallet | None = None
        self.user_by_email: object | None = None
        self.added: list[object] = []
        self.commits = 0
        self.rollbacks = 0

    async def get(self, model, pk):
        if model is Plan:
            return self.plans.get(pk)
        return None

    async def scalar(self, stmt):
        entity = stmt.column_descriptions[0].get("entity")
        if entity is Payment:
            if "idempotency_key =" in str(stmt):
                return self.payment_by_key
            return self.payment_by_provider
        if entity is Wallet:
            return self.wallet
        if entity is User:
            return self.user_by_email
        return None

    def add(self, obj) -> None:
        self.added.append(obj)
        if isinstance(obj, Payment):
            self.payment_by_key = obj
            self.payment_by_provider = obj
        elif isinstance(obj, Wallet):
            self.wallet = obj

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1

    def begin(self) -> FakeTransaction:
        return FakeTransaction()


class FakeProvider:
    name = "yookassa"

    def __init__(self, payment=None) -> None:
        self.calls: list[dict] = []
        self.payment = payment or yookassa_payment()

    async def create_payment(self, amount, currency, description=None, *, idempotency_key=None, customer_email=None):
        self.calls.append({
            "amount": amount,
            "currency": currency,
            "description": description,
            "idempotency_key": idempotency_key,
            "customer_email": customer_email,
        })
        return self.payment

    async def process_payment_webhook(self, payload: dict):
        payment = payload["object"]
        return payment["id"], PaymentStatus(payment["status"])


def yookassa_payment(
    *,
    payment_id="pay_1",
    url="https://yookassa.test/confirm",
    status="pending",
    amount="390.00",
    confirmation=True,
):
    return SimpleNamespace(
        id=payment_id,
        status=status,
        confirmation=SimpleNamespace(confirmation_url=url) if confirmation else None,
        cancellation_details=None,
        amount=SimpleNamespace(value=amount),
    )


def paid_plan(plan_id: int = 2) -> Plan:
    return Plan(
        id=plan_id,
        code="starter",
        name="Старт",
        price=Decimal("390"),
        currency="RUB",
        limits={"included_credits": 2000, "run_cap_credits": 2000},
    )


def pending_payment(plan: Plan, *, user_id: int = 1) -> Payment:
    payment = Payment(
        user_id=user_id,
        plan_id=plan.id,
        provider="yookassa",
        provider_payment_id="pay_1",
        amount=Decimal("390"),
        status=PaymentStatus.pending,
        idempotency_key="checkout-key-1",
    )
    payment.plan = plan
    return payment


def webhook_payload(status: str = "succeeded", payment_id: str = "pay_1") -> dict:
    return {
        "event": f"payment.{status}",
        "object": {"id": payment_id, "status": status},
    }


@pytest.mark.asyncio
async def test_checkout_passes_client_idempotency_key_to_provider() -> None:
    db = FakeDB()
    db.plans[2] = paid_plan()
    provider = FakeProvider()
    url = await BillingService(db, provider).create_plan_checkout(
        SimpleNamespace(id=1, email="buyer@example.com"), 2, "client-key-123456"
    )
    assert url == "https://yookassa.test/confirm"
    assert provider.calls[0]["idempotency_key"] == "client-key-123456"
    assert provider.calls[0]["amount"] == "390.00"
    assert provider.calls[0]["customer_email"] == "buyer@example.com"
    assert db.commits == 1
    saved = next(item for item in db.added if isinstance(item, Payment))
    assert saved.idempotency_key == "client-key-123456"
    assert saved.provider_payment_id == "pay_1"
    assert saved.amount == Decimal("390.00")


@pytest.mark.asyncio
async def test_checkout_uses_request_email_when_profile_email_missing() -> None:
    db = FakeDB()
    db.plans[2] = paid_plan()
    provider = FakeProvider()
    user = SimpleNamespace(id=1, email=None)
    url = await BillingService(db, provider).create_plan_checkout(
        user,
        2,
        "client-key-receipt",
        customer_email="  Receipt.User@Example.com ",
    )
    assert url == "https://yookassa.test/confirm"
    assert provider.calls[0]["customer_email"] == "receipt.user@example.com"
    assert user.email == "receipt.user@example.com"


@pytest.mark.asyncio
async def test_checkout_does_not_overwrite_existing_profile_email() -> None:
    db = FakeDB()
    db.plans[2] = paid_plan()
    user = SimpleNamespace(id=1, email="buyer@example.com")
    await BillingService(db, FakeProvider()).create_plan_checkout(
        user, 2, "client-key-keep-email", customer_email="other@example.com"
    )
    assert user.email == "buyer@example.com"


@pytest.mark.asyncio
async def test_checkout_rejects_email_taken_by_another_user() -> None:
    db = FakeDB()
    db.plans[2] = paid_plan()
    db.user_by_email = SimpleNamespace(id=99, email="taken@example.com")
    with pytest.raises(HTTPException) as error:
        await BillingService(db, FakeProvider()).create_plan_checkout(
            SimpleNamespace(id=1, email=None),
            2,
            "client-key-taken",
            customer_email="taken@example.com",
        )
    assert error.value.status_code == 409


@pytest.mark.asyncio
async def test_checkout_allows_email_already_on_same_user() -> None:
    """Параллельный/повторный checkout: в БД email уже у этого же user_id."""
    db = FakeDB()
    db.plans[2] = paid_plan()
    db.user_by_email = SimpleNamespace(id=1, email="mine@example.com")
    user = SimpleNamespace(id=1, email=None)
    url = await BillingService(db, FakeProvider()).create_plan_checkout(
        user, 2, "client-key-same-user", customer_email="mine@example.com"
    )
    assert url == "https://yookassa.test/confirm"
    assert user.email == "mine@example.com"
    assert db.commits == 1  # только Payment, email уже был в БД


@pytest.mark.asyncio
async def test_checkout_replay_returns_same_url_without_second_insert() -> None:
    db = FakeDB()
    plan = paid_plan()
    db.plans[2] = plan
    db.payment_by_key = pending_payment(plan)
    provider = FakeProvider()
    url = await BillingService(db, provider).create_plan_checkout(
        SimpleNamespace(id=1, email="buyer@example.com"), 2, "checkout-key-1"
    )
    assert url == "https://yookassa.test/confirm"
    assert provider.calls[0]["idempotency_key"] == "checkout-key-1"
    assert db.commits == 0
    assert not any(isinstance(item, Payment) for item in db.added)


@pytest.mark.asyncio
async def test_checkout_rejects_foreign_or_mismatched_idempotency_key() -> None:
    db = FakeDB()
    plan = paid_plan()
    db.plans[2] = plan
    db.plans[3] = paid_plan(3)
    db.payment_by_key = pending_payment(plan, user_id=9)
    with pytest.raises(HTTPException) as error:
        await BillingService(db, FakeProvider()).create_plan_checkout(
            SimpleNamespace(id=1, email="buyer@example.com"), 2, "checkout-key-1"
        )
    assert error.value.status_code == 409

    db.payment_by_key = pending_payment(plan)
    with pytest.raises(HTTPException) as error:
        await BillingService(db, FakeProvider()).create_plan_checkout(
            SimpleNamespace(id=1, email="buyer@example.com"), 3, "checkout-key-1"
        )
    assert error.value.status_code == 409


@pytest.mark.asyncio
async def test_checkout_rejects_free_plan_and_missing_confirmation() -> None:
    db = FakeDB()
    db.plans[1] = Plan(id=1, code="free", name="Пробный", price=Decimal("0"), currency="RUB", limits={})
    with pytest.raises(HTTPException) as error:
        await BillingService(db, FakeProvider()).create_plan_checkout(
            SimpleNamespace(id=1, email="buyer@example.com"), 1, "client-key-123456"
        )
    assert error.value.status_code == 404

    db.plans[2] = paid_plan()
    provider = FakeProvider(yookassa_payment(confirmation=False))
    with pytest.raises(HTTPException) as error:
        await BillingService(db, provider).create_plan_checkout(
            SimpleNamespace(id=1, email="buyer@example.com"), 2, "client-key-123456"
        )
    assert error.value.status_code == 400


@pytest.mark.asyncio
async def test_successful_webhook_credits_plan_credits_not_rubles() -> None:
    db = FakeDB()
    plan = paid_plan()
    db.payment_by_provider = pending_payment(plan)
    db.wallet = Wallet(user_id=1, balance=Decimal("100"), reserved=Decimal("0"))
    await BillingService(db, FakeProvider()).process_payment_webhook(webhook_payload())

    assert db.payment_by_provider.status == PaymentStatus.succeeded
    assert db.wallet.balance == Decimal("2100")
    ledger = next(item for item in db.added if isinstance(item, WalletLedger))
    assert ledger.kind == LedgerKind.purchase
    assert ledger.amount == Decimal("2000")
    assert ledger.idempotency_key == "purchase:pay_1"


@pytest.mark.asyncio
async def test_successful_webhook_creates_wallet() -> None:
    db = FakeDB()
    plan = paid_plan()
    db.payment_by_provider = pending_payment(plan)
    await BillingService(db, FakeProvider()).process_payment_webhook(webhook_payload())

    assert db.wallet is not None
    assert db.wallet.balance == Decimal("2000")


@pytest.mark.asyncio
async def test_webhook_is_idempotent_and_canceled_does_not_credit() -> None:
    db = FakeDB()
    plan = paid_plan()
    payment = pending_payment(plan)
    db.payment_by_provider = payment
    db.wallet = Wallet(user_id=1, balance=Decimal("100"), reserved=Decimal("0"))
    service = BillingService(db, FakeProvider())

    await service.process_payment_webhook(webhook_payload())
    await service.process_payment_webhook(webhook_payload())
    assert db.wallet.balance == Decimal("2100")
    assert sum(isinstance(item, WalletLedger) for item in db.added) == 1

    payment.status = PaymentStatus.pending
    db.added.clear()
    await service.process_payment_webhook(webhook_payload("canceled"))
    assert payment.status == PaymentStatus.canceled
    assert db.wallet.balance == Decimal("2100")
    assert not db.added


@pytest.mark.asyncio
async def test_webhook_unknown_payment_is_404() -> None:
    with pytest.raises(HTTPException) as error:
        await BillingService(FakeDB(), FakeProvider()).process_payment_webhook(webhook_payload())
    assert error.value.status_code == 404


@pytest.mark.asyncio
async def test_yookassa_webhook_accepts_valid_payload() -> None:
    provider = object.__new__(YooKassaProvider)
    payment_id, status = await provider.process_payment_webhook({
        "event": "payment.succeeded",
        "object": {"id": "pay_1", "status": "succeeded"},
    })
    assert payment_id == "pay_1"
    assert status == PaymentStatus.succeeded


@pytest.mark.asyncio
async def test_yookassa_webhook_rejects_invalid_payload() -> None:
    provider = object.__new__(YooKassaProvider)
    with pytest.raises(HTTPException) as error:
        await provider.process_payment_webhook({"event": "refund.succeeded", "object": {"id": "pay_1", "status": "succeeded"}})
    assert error.value.status_code == 400


def test_wallet_response_does_not_require_currency_on_model() -> None:
    wallet = Wallet(user_id=7, balance=Decimal("100"), reserved=Decimal("0"))
    response = WalletResponse.model_validate(wallet, from_attributes=True)
    assert response.user_id == 7
    assert response.balance == Decimal("100")
    assert response.currency == "CRD"


def test_scalar_query_shapes_are_recognized() -> None:
    assert "idempotency_key =" in str(select(Payment).where(Payment.idempotency_key == "x"))
    assert "provider_payment_id =" in str(select(Payment).where(Payment.provider_payment_id == "pay_1"))
