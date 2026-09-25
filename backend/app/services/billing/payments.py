from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from yookassa import Configuration
from yookassa.configuration import ConfigurationError
from yookassa.payment import PaymentResponse

from core.config import settings
from models.billing import LedgerKind, Payment, PaymentStatus, Plan, Wallet, WalletLedger
from models.user import User
from services.billing.subscriptions import SubscriptionService
from services.providers import PaymentProvider


class PaymentService:
    def __init__(self, db: AsyncSession, payment_provider: PaymentProvider | None = None):
        self.db = db
        self.payment_provider = payment_provider

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

        plan = await self.db.get(Plan, plan_id)
        if plan is not None and plan.price > 0:
            await SubscriptionService(self.db).ensure_can_buy(user.id, plan)

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
            subscription_kind = None
            if payment.plan is not None and payment.plan.price > 0:
                subscription_kind = await SubscriptionService(self.db).activate(payment.user_id, payment.plan)
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
                metadata_={
                    "plan_id": payment.plan_id,
                    "plan_code": payment.plan.code if payment.plan else None,
                    "plan_name": payment.plan.name if payment.plan else None,
                    "subscription": subscription_kind,
                },
            ))
