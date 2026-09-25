"""Месячные тарифы: период 30 дней, неиспользованные токены сгорают в конце периода.

Покупка без активного тарифа начинает период. Повторная покупка того же тарифа
продлевает его на период. Переход на более дорогой тариф начинает новый период,
токены с баланса сохраняются. Дешевле текущего купить нельзя, пока период не закончился.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.billing import LedgerKind, Plan, Subscription, Wallet, WalletLedger
from services.stored_images import MAX_USER_IMAGE_BYTES, MAX_USER_IMAGE_FILES

DEFAULT_PERIOD_DAYS = 30
MB = 1024 * 1024
FREE_STORAGE_LIMITS = (MAX_USER_IMAGE_FILES, MAX_USER_IMAGE_BYTES)
DOWNGRADE_BLOCKED = "Нельзя перейти на более дешёвый тариф, пока не закончился текущий период"


@dataclass(frozen=True)
class StorageLimits:
    max_files: int
    max_bytes: int


def _int_limit(limits: dict, key: str) -> int | None:
    raw = limits.get(key)
    try:
        value = int(Decimal(str(raw)))
    except Exception:
        return None
    return value if value > 0 else None


def storage_limits(plan: Plan | None) -> StorageLimits:
    limits = plan.limits if plan is not None and isinstance(plan.limits, dict) else {}
    files = _int_limit(limits, "max_files") or FREE_STORAGE_LIMITS[0]
    megabytes = _int_limit(limits, "max_storage_mb")
    return StorageLimits(files, megabytes * MB if megabytes else FREE_STORAGE_LIMITS[1])


def period_days(plan: Plan) -> int:
    limits = plan.limits if isinstance(plan.limits, dict) else {}
    return _int_limit(limits, "period_days") or DEFAULT_PERIOD_DAYS


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.UTC)


def is_active(subscription: Subscription | None, now: datetime.datetime | None = None) -> bool:
    return bool(
        subscription is not None
        and subscription.status == "active"
        and subscription.expires_at > (now or _now())
    )


class SubscriptionService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get(self, user_id: int, *, lock: bool = False) -> Subscription | None:
        query = select(Subscription).where(Subscription.user_id == user_id)
        return await self.db.scalar(query.with_for_update() if lock else query)

    async def active(self, user_id: int) -> Subscription | None:
        subscription = await self.get(user_id)
        return subscription if is_active(subscription) else None

    async def current_plan(self, user_id: int) -> Plan | None:
        subscription = await self.active(user_id)
        if subscription is not None:
            return subscription.plan or await self.db.get(Plan, subscription.plan_id)
        return await self.db.scalar(select(Plan).where(Plan.code == "free"))

    async def storage_limits(self, user_id: int) -> StorageLimits:
        return storage_limits(await self.current_plan(user_id))

    async def ensure_can_buy(self, user_id: int, plan: Plan) -> None:
        subscription = await self.active(user_id)
        if subscription is None:
            return
        current = subscription.plan or await self.db.get(Plan, subscription.plan_id)
        if current is not None and plan.price < current.price:
            raise HTTPException(409, DOWNGRADE_BLOCKED)

    async def activate(self, user_id: int, plan: Plan, now: datetime.datetime | None = None) -> str:
        """Начать, продлить или повысить тариф после оплаты. Возвращает new / renewal / upgrade."""
        now = now or _now()
        days = datetime.timedelta(days=period_days(plan))
        subscription = await self.get(user_id, lock=True)
        if subscription is None:
            self.db.add(Subscription(
                user_id=user_id,
                plan_id=plan.id,
                status="active",
                started_at=now,
                expires_at=now + days,
            ))
            return "new"
        if not is_active(subscription, now):
            if subscription.status == "active":
                await self._burn(subscription)
            kind = "new"
            subscription.started_at = now
            subscription.expires_at = now + days
            subscription.plan_id = plan.id
        else:
            current = subscription.plan or await self.db.get(Plan, subscription.plan_id)
            if current is not None and plan.price > current.price:
                kind = "upgrade"
                subscription.plan_id = plan.id
                subscription.started_at = now
                subscription.expires_at = max(subscription.expires_at, now + days)
            else:
                kind = "renewal"
                subscription.expires_at = subscription.expires_at + days
        subscription.plan = await self.db.get(Plan, subscription.plan_id)
        subscription.status = "active"
        subscription.reminded_at = None
        return kind

    async def expire_due(self, now: datetime.datetime | None = None, limit: int = 200) -> list[int]:
        """Закрывает истёкшие периоды и сжигает свободный остаток токенов. Идемпотентно."""
        now = now or _now()
        subscriptions = list(await self.db.scalars(
            select(Subscription)
            .where(Subscription.status == "active", Subscription.expires_at <= now)
            .order_by(Subscription.expires_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        ))
        expired: list[int] = []
        for subscription in subscriptions:
            await self._burn(subscription)
            subscription.status = "expired"
            expired.append(subscription.user_id)
        await self.db.commit()
        return expired

    async def _burn(self, subscription: Subscription) -> None:
        """Сжигает свободный остаток за закончившийся период. Резерв идущих запусков не трогаем."""
        key = f"expire:{subscription.id}:{subscription.expires_at.isoformat()}"
        if await self.db.scalar(select(WalletLedger.id).where(WalletLedger.idempotency_key == key)):
            return
        wallet = await self.db.scalar(select(Wallet).where(Wallet.user_id == subscription.user_id).with_for_update())
        burned = max(wallet.balance - wallet.reserved, Decimal("0")) if wallet else Decimal("0")
        if wallet is not None and burned > 0:
            wallet.balance -= burned
        self.db.add(WalletLedger(
            user_id=subscription.user_id,
            kind=LedgerKind.expire,
            amount=-burned,
            idempotency_key=key,
            reference=f"subscription:{subscription.id}",
            metadata_={"plan_id": subscription.plan_id, "expires_at": subscription.expires_at.isoformat()},
        ))

    async def due_for_reminder(self, within: datetime.timedelta, now: datetime.datetime | None = None) -> list[Subscription]:
        now = now or _now()
        return list(await self.db.scalars(
            select(Subscription).where(
                Subscription.status == "active",
                Subscription.reminded_at.is_(None),
                Subscription.expires_at > now,
                Subscription.expires_at <= now + within,
            )
        ))
