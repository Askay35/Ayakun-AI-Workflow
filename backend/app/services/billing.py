import datetime
import uuid
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy.orm import selectinload
from yookassa import Configuration
from yookassa.configuration import ConfigurationError
from yookassa.payment import PaymentResponse

from models.billing import (
    BillingReservation,
    LedgerKind,
    Payment,
    PaymentStatus,
    Plan,
    UsageRecord,
    Wallet,
    WalletLedger,
)
from models.user import User
from models.workflow import WorkflowRun
from core.config import settings
from services.providers import PaymentProvider
from services.pricing import quantize_credits


Configuration.account_id = settings.yookassa_account_id
Configuration.secret_key = settings.yookassa_secret_key

class BillingService:
    def __init__(self, db: AsyncSession, payment_provider: PaymentProvider | None = None):
        self.db = db
        self.payment_provider = payment_provider

    async def plans(self) -> list[Plan]:
        return list(await self.db.scalars(select(Plan).order_by(Plan.price)))

    async def run_cap(self, user: User) -> Decimal:
        return Decimal(str(settings.default_run_cap_credits))

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
        amount: Decimal | None = None,
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
        available = max(wallet.balance - wallet.reserved, Decimal("0"))
        needed = quantize_credits(amount) if amount is not None else cap
        if needed > cap:
            raise HTTPException(402, "Максимальная стоимость запуска превышает лимит")
        if needed > 0 and available < needed:
            raise HTTPException(402, "Недостаточно credits для запуска")
        amount = min(available, needed, cap) if needed > 0 else Decimal("0")
        if needed > 0 and amount <= 0:
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
        requested = quantize_credits(max(amount, Decimal("0")))
        if requested <= 0:
            return wallet
        chargeable = min(
            requested,
            reservation.remaining,
            wallet.reserved,
            max(wallet.balance, Decimal("0")),
        )
        chargeable = quantize_credits(chargeable)
        if chargeable <= 0:
            raise HTTPException(409, "Активный резерв исчерпан")
        amount = chargeable
        wallet.reserved -= amount
        wallet.balance -= amount
        reservation.charged += amount
        run = await self.db.get(WorkflowRun, workflow_run_id)
        if run:
            run.cost += amount
        payload = details or {}
        if requested > amount:
            payload = {**payload, "capped": True, "requested_credits": str(requested)}
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
        self, plan_id: int, idempotency_key: str, *, customer_email: str | None = None
    ) -> PaymentResponse:
        if not self.payment_provider:
            raise HTTPException(503, "Платежный провайдер не настроен")
        if settings.yookassa_account_id and settings.yookassa_secret_key:
            Configuration.account_id = settings.yookassa_account_id
            Configuration.secret_key = settings.yookassa_secret_key

        plan = await self.db.get(Plan, plan_id)
        if not plan or not plan.price > 0:
            raise HTTPException(404, "Тариф не найден")

        try:
            return await self.payment_provider.create_payment(
                f"{plan.price:.2f}",
                plan.currency.upper(),
                "Оплата тарифа " + plan.name,
                idempotency_key=idempotency_key,
                customer_email=customer_email,
            )
        except ConfigurationError as exc:
            raise HTTPException(503, "Платежный провайдер не настроен") from exc

    async def create_plan_checkout(
        self,
        user: User,
        plan_id: int,
        idempotency_key: str,
        *,
        customer_email: str | None = None,
    ) -> str:
        existing = await self.db.scalar(select(Payment).where(Payment.idempotency_key == idempotency_key))
        if existing:
            if existing.user_id != user.id or existing.plan_id != plan_id:
                raise HTTPException(409, "Idempotency key уже используется")

        receipt_email = (customer_email or getattr(user, "email", None) or "").strip().lower() or None
        email_attached = await self._attach_profile_email(user, receipt_email)
        payment = await self.create_payment(
            plan_id,
            idempotency_key,
            customer_email=receipt_email,
        )
        if not payment.confirmation or not payment.confirmation.confirmation_url:
            reason = payment.cancellation_details.reason if payment.cancellation_details else "причина неизвестна"
            raise HTTPException(400, "Не удалось создать платеж: " + reason)

        if not existing:
            normalized_status = payment.status if payment.status in PaymentStatus._value2member_map_ else "pending"
            self.db.add(Payment(
                user_id=user.id,
                plan_id=plan_id,
                provider=self.payment_provider.name,
                provider_payment_id=payment.id,
                amount=Decimal(payment.amount.value),
                status=PaymentStatus(normalized_status),
                idempotency_key=idempotency_key,
            ))
        if not existing or email_attached:
            try:
                await self.db.commit()
            except IntegrityError as exc:
                await self.db.rollback()
                if existing:
                    raise HTTPException(409, "Не удалось сохранить email") from exc
                # Повтор с тем же idempotency_key: платёж уже есть — отдаём URL.
                replay = await self.db.scalar(select(Payment).where(Payment.idempotency_key == idempotency_key))
                if replay and replay.user_id == user.id and replay.plan_id == plan_id:
                    return payment.confirmation.confirmation_url
                raise HTTPException(409, "Конфликт при создании платежа") from exc

        return payment.confirmation.confirmation_url

    async def _attach_profile_email(self, user: User, receipt_email: str | None) -> bool:
        if not receipt_email:
            return False
        current = (getattr(user, "email", None) or "").strip().lower()
        if current:
            return False
        # При повторном/параллельном checkout в БД почта уже может быть у этого же user.
        taken = await self.db.scalar(select(User).where(User.email == receipt_email))
        if taken is not None and taken.id != user.id:
            raise HTTPException(409, "Этот email уже занят другим аккаунтом")
        if taken is not None:
            user.email = receipt_email
            return False
        user.email = receipt_email
        return True

    def _plan_credits(self, plan: Plan | None) -> Decimal:
        if not plan:
            return Decimal("0")
        return Decimal(str((plan.limits or {}).get("included_credits", 0)))

    async def process_payment_webhook(self, payload: dict) -> None:
        if not self.payment_provider:
            raise HTTPException(503, "Платежный провайдер не настроен")

        payment_id, payment_status = await self.payment_provider.process_payment_webhook(payload)

        async with self.db.begin():
            payment = await self.db.scalar(
                select(Payment)
                .where(Payment.provider_payment_id == payment_id)
                .options(selectinload(Payment.plan))
                .with_for_update()
            )
            if not payment:
                raise HTTPException(404, "Платеж не найден")

            if payment.status == PaymentStatus.succeeded:
                return

            if payment_status != PaymentStatus.succeeded:
                payment.status = payment_status
                return

            payment.status = PaymentStatus.succeeded
            credits = self._plan_credits(payment.plan)
            wallet = await self.db.scalar(
                select(Wallet).where(Wallet.user_id == payment.user_id).with_for_update()
            )
            if not wallet:
                self.db.add(Wallet(
                    user_id=payment.user_id,
                    balance=credits,
                    reserved=Decimal("0"),
                ))
            else:
                wallet.balance += credits

            self.db.add(WalletLedger(
                user_id=payment.user_id,
                kind=LedgerKind.purchase,
                amount=credits,
                idempotency_key=f"purchase:{payment.provider_payment_id}",
                reference=payment.provider_payment_id,
            ))
