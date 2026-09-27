import uuid
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession
from yookassa.payment import PaymentResponse

from models.billing import BillingReservation, Plan, UsageRecord, Wallet, WalletLedger
from models.user import User
from services.billing.credits import CreditService
from services.billing.payments import PaymentService
from services.billing.wallet import WalletService
from services.providers import PaymentProvider


class BillingService:
    def __init__(self, db: AsyncSession, payment_provider: PaymentProvider | None = None):
        self.db = db
        self.payment_provider = payment_provider
        self.wallets = WalletService(db)
        self.credits = CreditService(db, self.wallets)
        self.payments = PaymentService(db, payment_provider)

    async def plans(self) -> list[Plan]:
        return await self.wallets.plans()

    async def run_cap(self, user: User) -> Decimal:
        return await self.wallets.run_cap(user)

    async def ledger(self, user: User) -> list[WalletLedger]:
        return await self.wallets.ledger(user)

    async def usage(self, user: User) -> list[UsageRecord]:
        return await self.wallets.usage(user)

    async def wallet(self, user: User, *, lock: bool = False) -> Wallet:
        return await self.wallets.wallet(user, lock=lock)

    async def ensure_initial_credit(self, user: User) -> Wallet:
        return await self.wallets.ensure_initial_credit(user)

    async def _already_applied(self, key: str) -> bool:
        return await self.wallets.already_applied(key)

    async def reserve(self, user: User, amount: Decimal, key: str, reference: str | None = None) -> Wallet:
        return await self.credits.reserve(user, amount, key, reference)

    async def reserve_run(
        self,
        user: User,
        workflow_run_id: uuid.UUID,
        request_id: str,
        amount: Decimal | None = None,
    ) -> BillingReservation:
        return await self.credits.reserve_run(user, workflow_run_id, request_id, amount)

    async def reservation_remaining(self, request_id: str) -> Decimal:
        return await self.credits.reservation_remaining(request_id)

    async def charge_reservation(
        self,
        user: User,
        reservation_request_id: str,
        amount: Decimal,
        request_id: str,
        *,
        workflow_run_id: uuid.UUID,
        units: int = 0,
        details: dict | None = None,
    ) -> Wallet:
        return await self.credits.charge_reservation(
            user,
            reservation_request_id,
            amount,
            request_id,
            workflow_run_id=workflow_run_id,
            units=units,
            details=details,
        )

    async def release_run(self, user: User, reservation_request_id: str, request_id: str) -> Wallet:
        return await self.credits.release_run(user, reservation_request_id, request_id)

    async def settle(
        self,
        user: User,
        amount: Decimal,
        key: str,
        reference: str | None = None,
        units: int = 0,
        workflow_run_id: uuid.UUID | None = None,
    ) -> Wallet:
        return await self.credits.settle(user, amount, key, reference, units, workflow_run_id)

    async def refund(self, user: User, amount: Decimal, key: str, reference: str | None = None) -> Wallet:
        return await self.credits.refund(user, amount, key, reference)

    async def set_balance(
        self,
        user: User,
        target: Decimal,
        key: str,
        *,
        actor: str,
        note: str | None = None,
    ) -> Wallet:
        return await self.credits.set_balance(user, target, key, actor=actor, note=note)

    async def release(self, user: User, amount: Decimal, key: str, reference: str | None = None) -> Wallet:
        return await self.credits.release(user, amount, key, reference)

    async def create_payment(
        self,
        plan_id: int,
        idempotency_key: str,
        *,
        customer_email: str | None = None,
        promo_code: str | None = None,
        user_id: int | None = None,
    ) -> tuple[PaymentResponse, int | None, int | None]:
        self.payments.payment_provider = self.payment_provider
        return await self.payments.create_payment(
            plan_id, idempotency_key, customer_email=customer_email, promo_code=promo_code, user_id=user_id
        )

    async def create_plan_checkout(
        self,
        user: User,
        plan_id: int,
        idempotency_key: str,
        *,
        customer_email: str | None = None,
        promo_code: str | None = None,
    ) -> str:
        self.payments.payment_provider = self.payment_provider
        return await self.payments.create_plan_checkout(
            user, plan_id, idempotency_key, customer_email=customer_email, promo_code=promo_code
        )

    async def process_payment_webhook(self, payload: dict) -> None:
        self.payments.payment_provider = self.payment_provider
        await self.payments.process_payment_webhook(payload)
