"""Реферальная программа.

Пригласивший получает бонус за каждую оплату тарифа приглашённым,
приглашённый — один раз, за первую оплату. Бонусы идут в wallet_ledger (kind=referral)
с идемпотентными ключами, поэтому повторная доставка вебхука ничего не удваивает.
"""

from __future__ import annotations

import datetime
import secrets
import string

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from models.billing import LedgerKind, Payment, PaymentStatus, Plan, Wallet, WalletLedger
from models.user import User
from schemas.referrals import ReferralItem, ReferralReward, ReferralSummary

CODE_ALPHABET = string.ascii_uppercase + string.digits
CODE_LENGTH = 8


def _new_code() -> str:
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))


def normalize_code(raw: str) -> str:
    return "".join(ch for ch in (raw or "").strip().upper() if ch in CODE_ALPHABET)[:16]


async def _credit(db: AsyncSession, user_id: int, key: str, metadata: dict) -> bool:
    if await db.scalar(select(WalletLedger.id).where(WalletLedger.idempotency_key == key)):
        return False
    amount = settings.referral_bonus_credits
    wallet = await db.scalar(select(Wallet).where(Wallet.user_id == user_id).with_for_update())
    if wallet is None:
        db.add(Wallet(user_id=user_id, balance=amount, reserved=0))
    else:
        wallet.balance += amount
    db.add(WalletLedger(
        user_id=user_id,
        kind=LedgerKind.referral,
        amount=amount,
        idempotency_key=key,
        reference=str(metadata.get("payment_id") or ""),
        metadata_=metadata,
    ))
    return True


async def reward_referral_payment(db: AsyncSession, payment: Payment) -> None:
    """Бонусы за оплаченный тариф приглашённого. Вызывается в транзакции вебхука оплаты."""
    if payment.plan is None or payment.plan.price <= 0:
        return
    payer = await db.get(User, payment.user_id)
    if payer is None or not payer.referred_by_id:
        return
    referrer = await db.get(User, payer.referred_by_id)
    if referrer is None or not referrer.is_active:
        return
    base = {"payment_id": str(payment.id), "plan_name": payment.plan.name}
    await _credit(db, referrer.id, f"referral:referrer:{payment.id}", {
        **base, "role": "referrer", "referee_id": payer.id, "referee_name": payer.name,
    })
    already_rewarded = await db.scalar(
        select(WalletLedger.id).where(
            WalletLedger.user_id == payer.id,
            WalletLedger.kind == LedgerKind.referral,
            WalletLedger.metadata_["role"].astext == "referee",
        ).limit(1)
    )
    if already_rewarded:
        return
    await _credit(db, payer.id, f"referral:referee:{payer.id}", {
        **base, "role": "referee", "referrer_id": referrer.id,
    })


class ReferralService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def code_for(self, user: User) -> str:
        if user.referral_code:
            return user.referral_code
        for _ in range(5):
            user.referral_code = _new_code()
            try:
                await self.db.commit()
                return user.referral_code
            except IntegrityError:
                await self.db.rollback()
        raise HTTPException(503, "Не удалось создать реферальный код, попробуйте ещё раз")

    async def claim(self, user: User, raw_code: str) -> None:
        code = normalize_code(raw_code)
        if not code:
            raise HTTPException(422, "Некорректный код приглашения")
        if user.referred_by_id:
            return
        referrer = await self.db.scalar(select(User).where(User.referral_code == code))
        if referrer is None or not referrer.is_active:
            raise HTTPException(404, "Код приглашения не найден")
        if referrer.id == user.id or referrer.referred_by_id == user.id:
            raise HTTPException(422, "Нельзя пригласить самого себя")
        window = datetime.timedelta(hours=settings.referral_claim_window_hours)
        if user.created_at < datetime.datetime.now(datetime.UTC) - window:
            raise HTTPException(409, "Приглашение действует только для новых аккаунтов")
        paid = await self.db.scalar(
            select(Payment.id)
            .join(Plan, Payment.plan_id == Plan.id)
            .where(Payment.user_id == user.id, Payment.status == PaymentStatus.succeeded, Plan.price > 0)
            .limit(1)
        )
        if paid:
            raise HTTPException(409, "Приглашение нельзя привязать после первой оплаты")
        user.referred_by_id = referrer.id
        await self.db.commit()

    async def summary(self, user: User) -> ReferralSummary:
        code = await self.code_for(user)
        referrals = list(await self.db.scalars(
            select(User).where(User.referred_by_id == user.id).order_by(User.created_at.desc())
        ))
        rewards = list(await self.db.scalars(
            select(WalletLedger)
            .where(WalletLedger.user_id == user.id, WalletLedger.kind == LedgerKind.referral)
            .order_by(WalletLedger.created_at.desc())
        ))
        earned_by_referee: dict[int, tuple[int, float]] = {}
        for reward in rewards:
            meta = reward.metadata_ or {}
            if meta.get("role") != "referrer":
                continue
            referee_id = int(meta.get("referee_id") or 0)
            count, total = earned_by_referee.get(referee_id, (0, 0.0))
            earned_by_referee[referee_id] = (count + 1, total + float(reward.amount))
        paid_counts = dict((await self.db.execute(
            select(Payment.user_id, func.count(Payment.id))
            .join(Plan, Payment.plan_id == Plan.id)
            .where(
                Payment.user_id.in_([item.id for item in referrals] or [0]),
                Payment.status == PaymentStatus.succeeded,
                Plan.price > 0,
            )
            .group_by(Payment.user_id)
        )).all())
        items = [
            ReferralItem(
                name=item.name,
                joined_at=item.created_at,
                purchases=int(paid_counts.get(item.id, 0)),
                earned=earned_by_referee.get(item.id, (0, 0.0))[1],
            )
            for item in referrals
        ]
        return ReferralSummary(
            code=code,
            bonus=float(settings.referral_bonus_credits),
            invited=len(items),
            paying=sum(1 for item in items if item.purchases > 0),
            earned=sum(float(reward.amount) for reward in rewards),
            referred=bool(user.referred_by_id),
            referrals=items,
            rewards=[
                ReferralReward(
                    amount=float(reward.amount),
                    role=str((reward.metadata_ or {}).get("role") or "referrer"),
                    referee_name=(reward.metadata_ or {}).get("referee_name"),
                    plan_name=(reward.metadata_ or {}).get("plan_name"),
                    created_at=reward.created_at,
                )
                for reward in rewards
            ],
        )
