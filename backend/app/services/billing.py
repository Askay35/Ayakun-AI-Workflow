import datetime
import uuid
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.billing import (
    BillingReservation,
    LedgerKind,
    Payment,
    PaymentStatus,
    Plan,
    Subscription,
    UsageRecord,
    Wallet,
    WalletLedger,
)
from models.user import User
from models.workflow import WorkflowRun
from core.config import settings
from services.providers import PaymentProvider
from services.pricing import quantize_credits


class BillingService:
    def __init__(self, db: AsyncSession, payment_provider: PaymentProvider | None = None):
        self.db = db
        self.payment_provider = payment_provider

    async def plans(self) -> list[Plan]:
        return list(await self.db.scalars(select(Plan).order_by(Plan.price)))

    async def subscription(self, user: User) -> Subscription | None:
        return await self.db.scalar(
            select(Subscription)
            .where(Subscription.user_id == user.id, Subscription.status == "active")
            .order_by(Subscription.starts_at.desc())
        )

    async def plan_limits(self, user: User) -> dict:
        await self.ensure_initial_credit(user)
        subscription = await self.subscription(user)
        if not subscription:
            return {}
        plan = await self.db.get(Plan, subscription.plan_id)
        return dict(plan.limits) if plan else {}

    async def run_cap(self, user: User) -> Decimal:
        subscription = await self.subscription(user)
        plan = await self.db.get(Plan, subscription.plan_id) if subscription else None
        limits = dict(plan.limits) if plan else {}
        return Decimal(str(limits.get("run_cap_credits", settings.default_run_cap_credits)))

    async def ledger(self, user: User) -> list[WalletLedger]:
        return list(await self.db.scalars(
            select(WalletLedger).where(WalletLedger.user_id == user.id).order_by(WalletLedger.created_at.desc())
        ))

    async def usage(self, user: User) -> list[UsageRecord]:
        return list(await self.db.scalars(
            select(UsageRecord).where(UsageRecord.user_id == user.id).order_by(UsageRecord.created_at.desc())
        ))

    async def wallet(self, user: User, *, lock: bool = False) -> Wallet:
        query = select(Wallet).where(Wallet.user_id == user.id)
        wallet = await self.db.scalar(query.with_for_update() if lock else query)
        if not wallet:
            wallet = Wallet(user_id=user.id)
            self.db.add(wallet)
            await self.db.flush()
        return wallet

    async def ensure_initial_credit(self, user: User) -> Wallet:
        wallet = await self.wallet(user, lock=True)
        free_plan = await self.db.scalar(select(Plan).where(Plan.code == "free"))
        initial_credits = Decimal(str(
            free_plan.limits.get("included_credits", settings.initial_token_balance)
            if free_plan else settings.initial_token_balance
        ))
        key = f"initial-credit:{user.id}"
        if not await self._already_applied(key):
            wallet.balance += initial_credits
            self.db.add(WalletLedger(
                user_id=user.id,
                kind=LedgerKind.credit,
                amount=initial_credits,
                idempotency_key=key,
                reference="free-plan",
            ))
        subscription = await self.subscription(user)
        if not subscription:
            if free_plan:
                self.db.add(Subscription(user_id=user.id, plan_id=free_plan.id))
        await self.db.commit()
        return wallet

    async def _already_applied(self, key: str) -> bool:
        return bool(await self.db.scalar(select(WalletLedger.id).where(WalletLedger.idempotency_key == key)))

    async def reserve(self, user: User, amount: Decimal, key: str, reference: str | None = None) -> Wallet:
        wallet = await self.wallet(user, lock=True)
        if await self._already_applied(key):
            return wallet
        if wallet.balance - wallet.reserved < amount:
            raise HTTPException(402, "Недостаточно средств")
        wallet.reserved += amount
        self.db.add(WalletLedger(
            user_id=user.id, kind=LedgerKind.reserve, amount=amount,
            idempotency_key=key, reference=reference,
        ))
        await self.db.commit()
        return wallet

    async def reserve_run(
        self,
        user: User,
        workflow_run_id: uuid.UUID,
        request_id: str,
    ) -> BillingReservation:
        existing = await self.db.scalar(
            select(BillingReservation).where(BillingReservation.request_id == request_id)
        )
        if existing:
            if existing.user_id != user.id or existing.workflow_run_id != workflow_run_id:
                raise HTTPException(409, "request_id уже используется")
            return existing
        cap = await self.run_cap(user)
        wallet = await self.wallet(user, lock=True)
        existing = await self.db.scalar(
            select(BillingReservation).where(BillingReservation.request_id == request_id)
        )
        if existing:
            if existing.user_id != user.id or existing.workflow_run_id != workflow_run_id:
                raise HTTPException(409, "request_id уже используется")
            return existing
        amount = min(max(wallet.balance - wallet.reserved, Decimal("0")), cap)
        if amount <= 0:
            raise HTTPException(402, "Недостаточно credits для запуска")
        reservation = BillingReservation(
            user_id=user.id,
            workflow_run_id=workflow_run_id,
            request_id=request_id,
            amount=amount,
            metadata_={"run_cap": str(cap)},
        )
        wallet.reserved += amount
        self.db.add(reservation)
        self.db.add(WalletLedger(
            user_id=user.id,
            kind=LedgerKind.reserve,
            amount=amount,
            idempotency_key=f"reserve:{request_id}",
            reference=str(workflow_run_id),
            metadata_={"reservation_request_id": request_id, "run_cap": str(cap)},
        ))
        await self.db.commit()
        return reservation

    async def reservation_remaining(self, request_id: str) -> Decimal:
        reservation = await self.db.scalar(
            select(BillingReservation).where(BillingReservation.request_id == request_id)
        )
        if not reservation or reservation.status != "active":
            return Decimal("0")
        return reservation.remaining

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
        wallet = await self.wallet(user, lock=True)
        if await self._already_applied(request_id):
            return wallet
        reservation = await self.db.scalar(
            select(BillingReservation)
            .where(BillingReservation.request_id == reservation_request_id)
            .with_for_update()
        )
        if not reservation or reservation.user_id != user.id or reservation.status != "active":
            raise HTTPException(409, "Активный резерв не найден")
        amount = quantize_credits(max(amount, Decimal("0")))
        if amount > reservation.remaining or amount > wallet.reserved or amount > wallet.balance:
            raise HTTPException(409, "Фактическая стоимость превышает резерв")
        wallet.reserved -= amount
        wallet.balance -= amount
        reservation.charged += amount
        run = await self.db.get(WorkflowRun, workflow_run_id)
        if run:
            run.cost += amount
        payload = details or {}
        self.db.add(WalletLedger(
            user_id=user.id,
            kind=LedgerKind.charge,
            amount=-amount,
            idempotency_key=request_id,
            reference=str(workflow_run_id),
            metadata_=payload,
        ))
        self.db.add(UsageRecord(
            user_id=user.id,
            workflow_run_id=workflow_run_id,
            units=units,
            cost=amount,
            idempotency_key=request_id,
            request_id=request_id,
            provider=payload.get("provider"),
            model=payload.get("model"),
            input_cache_hit_tokens=int(payload.get("input_cache_hit_tokens", 0)),
            input_cache_miss_tokens=int(payload.get("input_cache_miss_tokens", 0)),
            output_tokens=int(payload.get("output_tokens", 0)),
            provider_cost_usd=Decimal(str(payload.get("provider_cost_usd", 0))),
            details=payload,
        ))
        await self.db.commit()
        return wallet

    async def release_run(self, user: User, reservation_request_id: str, request_id: str) -> Wallet:
        wallet = await self.wallet(user, lock=True)
        if await self._already_applied(request_id):
            return wallet
        reservation = await self.db.scalar(
            select(BillingReservation)
            .where(BillingReservation.request_id == reservation_request_id)
            .with_for_update()
        )
        if not reservation or reservation.user_id != user.id:
            raise HTTPException(409, "Резерв не найден")
        released = reservation.remaining
        wallet.reserved = max(wallet.reserved - released, Decimal("0"))
        reservation.released += released
        reservation.status = "closed"
        reservation.closed_at = datetime.datetime.now(datetime.UTC)
        self.db.add(WalletLedger(
            user_id=user.id,
            kind=LedgerKind.release,
            amount=released,
            idempotency_key=request_id,
            reference=reservation_request_id,
        ))
        await self.db.commit()
        return wallet

    async def settle(
        self,
        user: User,
        amount: Decimal,
        key: str,
        reference: str | None = None,
        units: int = 0,
        workflow_run_id: uuid.UUID | None = None,
    ) -> Wallet:
        wallet = await self.wallet(user, lock=True)
        if await self._already_applied(key):
            return wallet
        if wallet.reserved < amount:
            raise HTTPException(409, "Сумма превышает резерв")
        wallet.reserved -= amount
        wallet.balance -= amount
        self.db.add(WalletLedger(
            user_id=user.id, kind=LedgerKind.settle, amount=-amount,
            idempotency_key=key, reference=reference,
        ))
        self.db.add(UsageRecord(
            user_id=user.id,
            workflow_run_id=workflow_run_id,
            units=units,
            cost=amount,
            idempotency_key=key,
        ))
        await self.db.commit()
        return wallet

    async def refund(self, user: User, amount: Decimal, key: str, reference: str | None = None) -> Wallet:
        wallet = await self.wallet(user, lock=True)
        if await self._already_applied(key):
            return wallet
        wallet.balance += amount
        self.db.add(WalletLedger(
            user_id=user.id, kind=LedgerKind.refund, amount=amount,
            idempotency_key=key, reference=reference,
        ))
        await self.db.commit()
        return wallet

    async def release(self, user: User, amount: Decimal, key: str, reference: str | None = None) -> Wallet:
        wallet = await self.wallet(user, lock=True)
        if await self._already_applied(key):
            return wallet
        released = min(amount, wallet.reserved)
        wallet.reserved -= released
        self.db.add(WalletLedger(
            user_id=user.id,
            kind=LedgerKind.release,
            amount=released,
            idempotency_key=key,
            reference=reference,
        ))
        await self.db.commit()
        return wallet

    async def create_payment(
        self, user: User, amount: Decimal, currency: str, idempotency_key: str
    ) -> Payment:
        existing = await self.db.scalar(select(Payment).where(Payment.idempotency_key == idempotency_key))
        if existing:
            if existing.user_id != user.id:
                raise HTTPException(409, "Idempotency key уже используется")
            return existing
        if not self.payment_provider:
            raise HTTPException(503, "Платежный провайдер не настроен")
        intent = await self.payment_provider.create_payment(
            f"{amount:.2f}", currency.upper(), idempotency_key, "Пополнение баланса Ayakun"
        )
        normalized_status = intent.status if intent.status in PaymentStatus._value2member_map_ else "pending"
        payment = Payment(
            user_id=user.id,
            provider_payment_id=intent.provider_id,
            amount=amount,
            currency=currency.upper(),
            status=PaymentStatus(normalized_status),
            idempotency_key=idempotency_key,
            confirmation_url=intent.confirmation_url,
        )
        self.db.add(payment)
        await self.db.commit()
        return payment

    async def create_plan_checkout(
        self,
        user: User,
        plan_id: int,
        idempotency_key: str,
    ) -> Payment:
        plan = await self.db.get(Plan, plan_id)
        if not plan or plan.code == "free":
            raise HTTPException(404, "Платный тариф не найден")
        payment = await self.create_payment(
            user,
            plan.price,
            plan.currency,
            idempotency_key,
        )
        if payment.plan_id not in (None, plan.id):
            raise HTTPException(409, "Idempotency key относится к другому тарифу")
        payment.plan_id = plan.id
        await self.db.commit()
        return payment

    async def process_yookassa_webhook(self, provider_payment_id: str) -> None:
        if not self.payment_provider:
            raise HTTPException(503, "Платежный провайдер не настроен")
        authoritative = await self.payment_provider.get_payment(provider_payment_id)
        payment = await self.db.scalar(
            select(Payment).where(Payment.provider_payment_id == provider_payment_id).with_for_update()
        )
        if not payment:
            raise HTTPException(404, "Платеж не найден")
        normalized_status = (
            authoritative.status if authoritative.status in PaymentStatus._value2member_map_ else "pending"
        )
        new_status = PaymentStatus(normalized_status)
        if payment.status == PaymentStatus.succeeded:
            return
        payment.status = new_status
        if new_status == PaymentStatus.succeeded:
            wallet = await self.db.scalar(select(Wallet).where(Wallet.user_id == payment.user_id).with_for_update())
            if not wallet:
                wallet = Wallet(user_id=payment.user_id)
                self.db.add(wallet)
                await self.db.flush()
            key = f"payment:{provider_payment_id}"
            if not await self._already_applied(key):
                if payment.plan_id:
                    plan = await self.db.get(Plan, payment.plan_id)
                    token_amount = Decimal(str(plan.limits.get("included_credits", 0)))
                    active = list(await self.db.scalars(
                        select(Subscription).where(
                            Subscription.user_id == payment.user_id,
                            Subscription.status == "active",
                        )
                    ))
                    now = datetime.datetime.now(datetime.UTC)
                    for subscription in active:
                        subscription.status = "expired"
                        subscription.ends_at = now
                    self.db.add(Subscription(
                        user_id=payment.user_id,
                        plan_id=payment.plan_id,
                        starts_at=now,
                        ends_at=now + datetime.timedelta(days=30),
                    ))
                else:
                    token_amount = payment.amount * settings.payment_credits_per_usd
                wallet.balance += token_amount
                self.db.add(WalletLedger(
                    user_id=payment.user_id,
                    kind=LedgerKind.purchase,
                    amount=token_amount,
                    idempotency_key=key,
                    reference=str(payment.id),
                ))
        await self.db.commit()

    async def process_payment_webhook(self, payload: dict) -> None:
        if not self.payment_provider:
            raise HTTPException(503, "Платежный провайдер не настроен")
        provider_payment_id = self.payment_provider.parse_webhook(payload)
        await self.process_yookassa_webhook(provider_payment_id)
