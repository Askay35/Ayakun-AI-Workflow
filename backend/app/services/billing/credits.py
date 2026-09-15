import datetime
import uuid
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.billing import BillingReservation, LedgerKind, UsageRecord, Wallet, WalletLedger
from models.user import User
from models.workflow import WorkflowRun
from services.billing.wallet import WalletService
from services.pricing import quantize_credits


class CreditService:
    def __init__(self, db: AsyncSession, wallets: WalletService):
        self.db = db
        self.wallets = wallets

    async def reserve(self, user: User, amount: Decimal, key: str, reference: str | None = None) -> Wallet:
        wallet = await self.wallets.wallet(user, lock=True)
        if await self.wallets.already_applied(key):
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
        cap = await self.wallets.run_cap(user)
        wallet = await self.wallets.wallet(user, lock=True)
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
        wallet = await self.wallets.wallet(user, lock=True)
        if await self.wallets.already_applied(request_id):
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
        wallet = await self.wallets.wallet(user, lock=True)
        if await self.wallets.already_applied(request_id):
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
        wallet = await self.wallets.wallet(user, lock=True)
        if await self.wallets.already_applied(key):
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
        wallet = await self.wallets.wallet(user, lock=True)
        if await self.wallets.already_applied(key):
            return wallet
        wallet.balance += amount
        self.db.add(WalletLedger(
            user_id=user.id, kind=LedgerKind.refund, amount=amount,
            idempotency_key=key, reference=reference,
        ))
        await self.db.commit()
        return wallet

    async def release(self, user: User, amount: Decimal, key: str, reference: str | None = None) -> Wallet:
        wallet = await self.wallets.wallet(user, lock=True)
        if await self.wallets.already_applied(key):
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
